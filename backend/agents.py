"""The five Campus Customs agents, with real any-to-any delegation.

Full connectivity is implemented, not merely described in the prompts: every
agent is given the same `delegate` tool, whose target is any of the five
roles, and calling it actually executes the target agent and returns its
structured result.

Loop safety is enforced here in code rather than by asking the model nicely.
A single `RunState` threads through every agent and tool call in a run and
holds the counters; when a cap is hit the delegation or tool call is refused
with an explanatory message the agent can act on, so a run degrades into an
honest limitation instead of spinning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.mcp import MCPToolset, StdioTransport
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from . import config
from .audit import append_event, summarize_result
from .models import AgentName, AgentResult, TicketResolution

# --------------------------------------------------------------- run state


@dataclass
class RunState:
    """Per-ticket counters shared by every agent in one run.

    One instance is created per ticket run and passed as `deps` to every
    agent, so the caps are global to the run rather than per agent.
    """

    run_id: str
    ticket_id: int | None = None
    step: int = 0
    delegations_used: int = 0
    tool_calls_used: int = 0
    max_depth_reached: int = 0
    agents_involved: list[AgentName] = field(default_factory=list)
    pair_counts: dict[str, int] = field(default_factory=dict)
    active_chain: list[AgentName] = field(default_factory=list)
    limit_hits: list[str] = field(default_factory=list)

    def next_step(self) -> int:
        self.step += 1
        return self.step

    def note_agent(self, agent: AgentName) -> None:
        if agent not in self.agents_involved:
            self.agents_involved.append(agent)

    def note_limit(self, which: str) -> None:
        if which not in self.limit_hits:
            self.limit_hits.append(which)


# ------------------------------------------------------------------ model


def build_model() -> OpenAIChatModel:
    """The single model every agent uses, reached through Portkey.

    The API key is read from the environment at call time and is never
    written to source, logs or the audit trail.
    """
    provider = OpenAIProvider(
        base_url=config.PORTKEY_BASE_URL,
        api_key=config.get_portkey_api_key(),
    )
    # gpt-6-luna rejects function tools on /v1/chat/completions unless
    # reasoning_effort is 'none'; every agent in this system uses tools.
    return OpenAIChatModel(
        config.MODEL_NAME,
        provider=provider,
        settings=OpenAIChatModelSettings(
            openai_reasoning_effort=config.REASONING_EFFORT
        ),
    )


# ------------------------------------------------------- MCP tool plumbing


async def _process_tool_call(
    ctx: RunContext[RunState],
    call_tool: Any,
    name: str,
    args: dict[str, Any],
) -> Any:
    """Wrap every MCP call: enforce the cap, audit it, bound the result.

    This is the single choke point through which all shop facts flow, which
    is what makes the audit trail automatic - an agent cannot call a tool
    without being logged, because it has no other route to the database.
    """
    state = ctx.deps
    agent_name = state.active_chain[-1].value if state.active_chain else "unknown"

    if state.tool_calls_used >= config.MAX_TOOL_CALLS_PER_RUN:
        state.note_limit("max_tool_calls_per_run")
        append_event(
            run_id=state.run_id,
            ticket_id=state.ticket_id,
            step=state.next_step(),
            agent=agent_name,
            event_type="tool_call_refused",
            tool_name=name,
            arguments_summary=args,
            stop_reason="limit_reached:max_tool_calls_per_run",
        )
        return {
            "error": "tool_call_limit_reached",
            "limit": config.MAX_TOOL_CALLS_PER_RUN,
            "guidance": (
                "No further MCP calls are available in this run. Report what you "
                "have already verified and record the rest as a limitation."
            ),
        }

    state.tool_calls_used += 1
    append_event(
        run_id=state.run_id,
        ticket_id=state.ticket_id,
        step=state.next_step(),
        agent=agent_name,
        event_type="mcp_tool_call",
        tool_name=name,
        arguments_summary=args,
    )

    result = await call_tool(name, args)

    # Bound what goes back into the model's context.
    try:
        text = json.dumps(result, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(result)

    truncated = False
    if len(text) > config.MAX_TOOL_RESULT_CHARS:
        truncated = True
        result = {
            "truncated": True,
            "reason": (
                f"Result exceeded MAX_TOOL_RESULT_CHARS="
                f"{config.MAX_TOOL_RESULT_CHARS}; showing the first portion."
            ),
            "partial_result": text[: config.MAX_TOOL_RESULT_CHARS],
        }

    append_event(
        run_id=state.run_id,
        ticket_id=state.ticket_id,
        step=state.next_step(),
        agent=agent_name,
        event_type="mcp_tool_result",
        tool_name=name,
        result_summary=summarize_result(result),
        detail="result truncated to fit the result cap" if truncated else None,
    )
    return result


def build_mcp_toolset() -> MCPToolset:
    """The shared campus-customs MCP server - the only path to shop data."""
    transport = StdioTransport(
        command=str(config.HW5_ROOT / ".venv" / "Scripts" / "python.exe"),
        args=[str(config.MCP_SERVER_SCRIPT)],
        cwd=str(config.HW5_ROOT),
    )
    return MCPToolset(transport, process_tool_call=_process_tool_call)


# ----------------------------------------------------------------- prompts


def load_prompt(agent: AgentName) -> str:
    """Read one agent's system prompt from backend/prompts/."""
    path = config.PROMPTS_DIR / f"{agent.value}.md"
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt file for {agent.value}: {path}")
    return path.read_text(encoding="utf-8")


# ------------------------------------------------------------ agent registry

AGENTS: dict[AgentName, Agent] = {}

_SPECIALISTS = (
    AgentName.INVENTORY,
    AgentName.ACCOUNTING,
    AgentName.FACILITIES,
    AgentName.CUSTOMER_SERVICE,
)


def _pair_key(src: AgentName, dst: AgentName) -> str:
    return f"{src.value}->{dst.value}"


async def _delegate_impl(
    ctx: RunContext[RunState],
    target_agent: AgentName,
    task: str,
    ticket_id: int | None,
    context: str | None,
) -> AgentResult:
    """Actually run the target agent. Shared by all five `delegate` tools."""
    state = ctx.deps
    source = state.active_chain[-1] if state.active_chain else AgentName.BOSS
    depth = len(state.active_chain)

    def refuse(reason: str, guidance: str) -> AgentResult:
        state.note_limit(reason)
        append_event(
            run_id=state.run_id,
            ticket_id=ticket_id or state.ticket_id,
            step=state.next_step(),
            agent=source.value,
            event_type="delegation_refused",
            from_agent=source.value,
            to_agent=target_agent.value,
            depth=depth,
            stop_reason=f"limit_reached:{reason}",
            detail=guidance,
        )
        return AgentResult(
            agent=target_agent,
            ticket_id=ticket_id or state.ticket_id,
            summary=f"Delegation refused: {guidance}",
            limitations=[
                {"issue": f"Delegation limit reached ({reason}).", "impact": guidance}
            ],
        )

    if target_agent == source:
        return refuse(
            "self_delegation",
            "An agent cannot delegate to itself. Answer directly or ask a "
            "different specialist.",
        )

    if target_agent in state.active_chain:
        return refuse(
            "circular_delegation",
            f"{target_agent.value} is already active higher in this delegation "
            f"chain; completing the loop would deadlock. Answer with what you have.",
        )

    if depth >= config.MAX_DELEGATION_DEPTH:
        return refuse(
            "max_delegation_depth",
            f"Delegation depth cap of {config.MAX_DELEGATION_DEPTH} reached. "
            f"Answer from the evidence already gathered.",
        )

    if state.delegations_used >= config.MAX_TOTAL_DELEGATIONS:
        return refuse(
            "max_total_delegations",
            f"This run has used its {config.MAX_TOTAL_DELEGATIONS} delegations. "
            f"Conclude with current evidence and note what is unresolved.",
        )

    key = _pair_key(source, target_agent)
    if state.pair_counts.get(key, 0) >= config.MAX_REPEAT_DELEGATIONS_PER_PAIR:
        return refuse(
            "max_repeat_delegations_per_pair",
            f"{key} has already been used "
            f"{config.MAX_REPEAT_DELEGATIONS_PER_PAIR} times for this run. "
            f"Do not ask the same specialist again.",
        )

    if context and len(context) > config.MAX_DELEGATION_CONTEXT_CHARS:
        context = (
            context[: config.MAX_DELEGATION_CONTEXT_CHARS]
            + " ... <context truncated: send a focused request, not a transcript>"
        )

    # Accepted - record and dispatch.
    state.delegations_used += 1
    state.pair_counts[key] = state.pair_counts.get(key, 0) + 1
    effective_ticket = ticket_id or state.ticket_id

    append_event(
        run_id=state.run_id,
        ticket_id=effective_ticket,
        step=state.next_step(),
        agent=source.value,
        event_type="delegation_sent",
        from_agent=source.value,
        to_agent=target_agent.value,
        depth=depth,
        arguments_summary={"task": task, "context": context},
    )

    prompt = f"Ticket {effective_ticket}. Task from {source.value}: {task}"
    if context:
        prompt += f"\n\nContext provided by {source.value}:\n{context}"

    state.active_chain.append(target_agent)
    state.note_agent(target_agent)
    state.max_depth_reached = max(state.max_depth_reached, len(state.active_chain) - 1)
    try:
        run = await AGENTS[target_agent].run(
            prompt,
            deps=state,
            usage_limits=UsageLimits(request_limit=config.MAX_AGENT_LOOP_STEPS),
        )
        result: AgentResult = run.output
    except Exception as exc:  # noqa: BLE001 - surfaced as a limitation, not a crash
        append_event(
            run_id=state.run_id,
            ticket_id=effective_ticket,
            step=state.next_step(),
            agent=target_agent.value,
            event_type="delegation_failed",
            from_agent=source.value,
            to_agent=target_agent.value,
            depth=depth,
            stop_reason=f"error:{type(exc).__name__}",
            detail=str(exc),
        )
        return AgentResult(
            agent=target_agent,
            ticket_id=effective_ticket,
            summary=f"{target_agent.value} could not complete the task.",
            limitations=[
                {
                    "issue": f"{type(exc).__name__} while running "
                    f"{target_agent.value}.",
                    "impact": "This specialist's input is missing from the answer.",
                }
            ],
        )
    finally:
        state.active_chain.pop()

    append_event(
        run_id=state.run_id,
        ticket_id=effective_ticket,
        step=state.next_step(),
        agent=target_agent.value,
        event_type="delegation_result",
        from_agent=target_agent.value,
        to_agent=source.value,
        depth=depth,
        result_summary=result.summary,
        detail=(
            f"facts={len(result.verified_facts)} "
            f"calcs={len(result.calculations)} "
            f"limits={len(result.limitations)}"
        ),
    )
    return result


def _attach_delegate_tool(agent: Agent) -> None:
    """Give one agent the ability to call any of the other four."""

    @agent.tool
    async def delegate(  # noqa: D401 - docstring is the tool description
        ctx: RunContext[RunState],
        target_agent: AgentName,
        task: str,
        ticket_id: int | None = None,
        context: str | None = None,
    ) -> AgentResult:
        """Ask another Campus Customs agent for help and get its result back.

        Send one focused question, not a transcript. The target agent runs for
        real, calls its own MCP tools, and returns structured verified facts,
        calculations, a recommendation and limitations.

        Args:
            target_agent: boss, inventory, accounting, facilities or
                customer_service.
            task: The specific question or task for that agent.
            ticket_id: The ticket this concerns.
            context: Only facts the target cannot look up itself.
        """
        if not task or not task.strip():
            raise ModelRetry("delegate requires a non-empty task.")
        return await _delegate_impl(ctx, target_agent, task, ticket_id, context)


def build_agents() -> dict[AgentName, Agent]:
    """Construct all five agents with full any-to-any connectivity.

    Returns the shared registry, populated. Called once per process; the
    registry is what `delegate` looks the target up in.
    """
    if AGENTS:
        return AGENTS

    model = build_model()
    toolset = build_mcp_toolset()

    AGENTS[AgentName.BOSS] = Agent(
        model,
        name="boss",
        deps_type=RunState,
        output_type=TicketResolution,
        instructions=load_prompt(AgentName.BOSS),
        toolsets=[toolset],
    )

    for role in _SPECIALISTS:
        AGENTS[role] = Agent(
            model,
            name=role.value,
            deps_type=RunState,
            output_type=AgentResult,
            instructions=load_prompt(role),
            toolsets=[toolset],
        )

    # Full connectivity: every agent gets the same delegate tool, and the
    # target enum covers all five roles.
    for agent in AGENTS.values():
        _attach_delegate_tool(agent)

    return AGENTS


def connectivity_matrix() -> dict[str, list[str]]:
    """Who can delegate to whom. Used by the verification script."""
    agents = build_agents()
    return {
        src.value: [dst.value for dst in agents if dst != src] for src in agents
    }
