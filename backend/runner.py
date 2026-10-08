"""Entry point for running the Campus Customs agent team on a ticket.

Usage:
    python -m backend.runner 101
    python -m backend.runner 101 102 103

The Boss agent receives the ticket, delegates to whichever specialists it
needs, and returns a TicketResolution. Run start, finish and every stop
reason are written to the append-only audit trail by this module; the agents
are never asked to log anything themselves.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone

from pydantic_ai.usage import UsageLimits

from . import config
from .agents import AGENTS, RunState, build_agents, build_mcp_toolset
from .audit import append_event
from .models import AgentName, RunOutcome

_TICKET_BRIEF = (
    "Handle ticket {ticket_id} for Campus Customs. Establish what the ticket "
    "asks, get the facts from the MCP tools, delegate to the specialists whose "
    "domain it falls in, and return the final resolution. Keep verified facts, "
    "deterministic calculations and your own judgement clearly separate."
)


async def run_ticket(ticket_id: int, *, run_id: str | None = None) -> RunOutcome:
    """Run the full agent team on one ticket and return a structured outcome."""
    run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    state = RunState(run_id=run_id, ticket_id=ticket_id)
    state.active_chain.append(AgentName.BOSS)
    state.note_agent(AgentName.BOSS)

    outcome = RunOutcome(
        run_id=run_id,
        ticket_id=ticket_id,
        model=config.MODEL_NAME,
        completed=False,
        stop_reason="not_started",
    )

    append_event(
        run_id=run_id,
        ticket_id=ticket_id,
        step=state.next_step(),
        agent=AgentName.BOSS.value,
        event_type="run_started",
        arguments_summary=config.limits_summary(),
    )

    agents = build_agents()
    boss = agents[AgentName.BOSS]

    try:
        async with asyncio.timeout(config.RUN_TIMEOUT_SECONDS):
            result = await boss.run(
                _TICKET_BRIEF.format(ticket_id=ticket_id),
                deps=state,
                usage_limits=UsageLimits(request_limit=config.MAX_AGENT_LOOP_STEPS),
            )
        resolution = result.output
        # The harness knows which agents actually ran; the model's own list is
        # self-reported and has been observed to omit participants. Trust the
        # counters, not the narrative.
        resolution.agents_involved = list(state.agents_involved)
        outcome.resolution = resolution
        outcome.completed = True
        outcome.stop_reason = (
            "completed"
            if not state.limit_hits
            else "completed_with_limits:" + ",".join(state.limit_hits)
        )
    except TimeoutError:
        outcome.stop_reason = "limit_reached:run_timeout_seconds"
        outcome.error = (
            f"Run exceeded RUN_TIMEOUT_SECONDS={config.RUN_TIMEOUT_SECONDS}."
        )
    except Exception as exc:  # noqa: BLE001 - reported honestly, not swallowed
        outcome.stop_reason = f"error:{type(exc).__name__}"
        outcome.error = str(exc)

    outcome.steps_used = state.step
    outcome.delegations_used = state.delegations_used
    outcome.max_depth_reached = state.max_depth_reached
    outcome.finished_at = datetime.now(timezone.utc).isoformat()

    append_event(
        run_id=run_id,
        ticket_id=ticket_id,
        step=state.next_step(),
        agent=AgentName.BOSS.value,
        event_type="run_finished",
        stop_reason=outcome.stop_reason,
        result_summary=(
            outcome.resolution.recommendation.summary
            if outcome.resolution is not None
            else outcome.error
        ),
        detail=(
            f"steps={outcome.steps_used} "
            f"delegations={outcome.delegations_used} "
            f"tool_calls={state.tool_calls_used} "
            f"max_depth={outcome.max_depth_reached}"
        ),
    )
    return outcome


async def run_tickets(ticket_ids: list[int]) -> list[RunOutcome]:
    """Run tickets one after another, sharing a single MCP server process."""
    build_agents()
    outcomes = []
    # One MCP subprocess for the whole batch rather than one per ticket.
    async with build_mcp_toolset():
        for tid in ticket_ids:
            outcomes.append(await run_ticket(tid))
    return outcomes


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    try:
        ticket_ids = [int(a) for a in argv]
    except ValueError:
        print("Ticket ids must be integers, e.g. 101 102 103", file=sys.stderr)
        return 2

    outcomes = asyncio.run(run_tickets(ticket_ids))
    for outcome in outcomes:
        print(json.dumps(outcome.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0 if all(o.completed for o in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
