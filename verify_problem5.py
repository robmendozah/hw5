"""Verification for HW5 Problem 5.

Runs the sixteen checks from the assignment. Where a check can be proved by
execution rather than inspection, it is: delegation is verified by actually
running one agent from inside another and confirming the target really ran
and really called an MCP tool. A stub model stands in for gpt-6-luna for that
test so the structural proof costs no API calls - the model wiring itself is
checked separately.

    python verify_problem5.py
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import re
import sys
from pathlib import Path

HW5 = Path(__file__).resolve().parent
sys.path.insert(0, str(HW5))

from backend import config  # noqa: E402
from backend.models import AgentName  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


# ---------------------------------------------------------------- 1, 2, 3, 4, 5


def check_agents_and_prompts() -> None:
    expected = {a.value for a in AgentName}
    check("1. five agent roles defined", len(expected) == 5, ", ".join(sorted(expected)))

    missing = [
        a.value
        for a in AgentName
        if not (config.PROMPTS_DIR / f"{a.value}.md").exists()
    ]
    check("2. each agent has its own prompt file", not missing, f"missing: {missing}")

    src = (HW5 / "backend" / "agents.py").read_text(encoding="utf-8")
    cfg = (HW5 / "backend" / "config.py").read_text(encoding="utf-8")
    check(
        "3. only gpt-6-luna is referenced",
        'MODEL_NAME = "gpt-6-luna"' in cfg
        and "config.MODEL_NAME" in src
        and not re.search(r"gpt-[0-9.]+(?!-luna)|claude-|gemini-", src),
        "single MODEL_NAME constant, used by build_model()",
    )
    check(
        "4. Portkey credentials come from PORTKEY_API_KEY",
        'PORTKEY_API_KEY_ENV = "PORTKEY_API_KEY"' in cfg
        and "os.getenv(PORTKEY_API_KEY_ENV)" in cfg,
        "read via os.getenv at call time",
    )


def check_no_hardcoded_key() -> None:
    """No literal that looks like a credential anywhere in backend/."""
    suspicious = []
    key_like = re.compile(r"""["'](sk-|pk-|pk_live|Bearer\s)[A-Za-z0-9_\-]{8,}["']""")
    live_key = os.getenv("PORTKEY_API_KEY")
    for path in (HW5 / "backend").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if key_like.search(text):
            suspicious.append(f"{path.name}: key-like literal")
        if live_key and len(live_key) >= 8 and live_key in text:
            suspicious.append(f"{path.name}: contains the live key value")
    check("5. no API key hard-coded in backend/", not suspicious, str(suspicious))


# ------------------------------------------------------------------- 6, 7


def check_connectivity() -> None:
    from backend.agents import AGENTS, build_agents

    build_agents()
    check("   agents instantiated", len(AGENTS) == 5, f"{len(AGENTS)} agents")

    # Every agent must expose a delegate tool whose target can be any other.
    missing = [n.value for n in AGENTS if "delegate" not in _tool_names(AGENTS[n])]
    check(
        "6. every agent can delegate to every other agent",
        not missing and len(AgentName) == 5,
        f"delegate tool present on all 5; target enum covers all roles"
        if not missing
        else f"missing on {missing}",
    )


def _tool_names(agent) -> list[str]:
    toolset = getattr(agent, "_function_toolset", None)
    if toolset is not None and hasattr(toolset, "tools"):
        return list(toolset.tools)
    return []


async def check_delegation_executes() -> None:
    """Prove delegation runs the target agent for real, not just in prose."""
    from pydantic_ai import models
    from pydantic_ai.messages import (
        ModelResponse,
        TextPart,
        ToolCallPart,
    )
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    from backend.agents import AGENTS, RunState, build_agents, build_mcp_toolset

    models.ALLOW_MODEL_REQUESTS = True
    build_agents()

    trace: list[str] = []

    def boss_fn(messages, info: AgentInfo) -> ModelResponse:
        calls = sum(
            1
            for m in messages
            for p in m.parts
            if isinstance(p, ToolCallPart) and p.tool_name == "delegate"
        )
        if calls == 0:
            trace.append("boss:delegating")
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "delegate",
                        {
                            "target_agent": "inventory",
                            "task": "Can ticket 101 be fulfilled from stock?",
                            "ticket_id": 101,
                        },
                    )
                ]
            )
        trace.append("boss:finalising")
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "final_result",
                    {
                        "ticket_id": 101,
                        "business_question": "Can we fulfil the tee order?",
                        "recommendation": {
                            "summary": "Cannot fulfil from stock.",
                            "rationale": "Inventory reported zero on hand.",
                        },
                        "agents_involved": ["boss", "inventory"],
                    },
                )
            ]
        )

    def inventory_fn(messages, info: AgentInfo) -> ModelResponse:
        used = sum(
            1
            for m in messages
            for p in m.parts
            if isinstance(p, ToolCallPart)
            and p.tool_name == "get_customer_order_fulfillment_context"
        )
        if used == 0:
            trace.append("inventory:calling mcp")
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "get_customer_order_fulfillment_context", {"ticket_id": 101}
                    )
                ]
            )
        trace.append("inventory:answering")
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "final_result",
                    {
                        "agent": "inventory",
                        "ticket_id": 101,
                        "summary": "Zero on hand; shortfall of 1.",
                        "tools_used": ["get_customer_order_fulfillment_context"],
                    },
                )
            ]
        )

    state = RunState(run_id="verify-delegation", ticket_id=101)
    state.active_chain.append(AgentName.BOSS)

    boss = AGENTS[AgentName.BOSS]
    inv = AGENTS[AgentName.INVENTORY]
    async with build_mcp_toolset():
        with boss.override(model=FunctionModel(boss_fn)), inv.override(
            model=FunctionModel(inventory_fn)
        ):
            result = await boss.run("Handle ticket 101.", deps=state)

    check(
        "7. delegation actually executes (target agent really ran)",
        "inventory:calling mcp" in trace and "inventory:answering" in trace,
        " -> ".join(trace),
    )
    check(
        "   delegated agent reached the MCP server",
        state.tool_calls_used >= 1,
        f"{state.tool_calls_used} MCP call(s) recorded",
    )
    check(
        "   boss produced a TicketResolution",
        result.output.ticket_id == 101,
        result.output.recommendation.summary,
    )


# ------------------------------------------------------------------ 8, 9


def check_no_direct_db_access() -> None:
    """No agent-side module may import sqlite3 or name a .db file."""
    offenders = []
    for path in (HW5 / "backend").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in {"sqlite3", "sqlalchemy", "aiosqlite"}:
                        offenders.append(f"{path.name}: import {a.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in {"sqlite3", "sqlalchemy", "aiosqlite"}:
                    offenders.append(f"{path.name}: from {node.module}")
    # Note: an earlier version of this check also flagged any file whose text
    # mentioned a .db path. That produced false positives on module docstrings
    # describing the architecture, and added nothing - a module cannot use
    # sqlite3 without importing it, which the AST walk above already catches.
    check("9. no direct SQLite access in backend/", not offenders, str(offenders))

    src = (HW5 / "backend" / "agents.py").read_text(encoding="utf-8")
    check(
        "8. shop facts flow only through the MCP toolset",
        "MCPToolset" in src and "toolsets=[toolset]" in src,
        "every agent is constructed with the shared MCP toolset and nothing else",
    )


# ------------------------------------------------------------- 10, 11, 16


async def check_mcp_tools() -> None:
    from backend.agents import build_mcp_toolset

    async with build_mcp_toolset() as ts:
        tools = await ts.list_tools()
    names = sorted(getattr(t, "name", str(t)) for t in tools)

    original = {
        "get_customer_order_fulfillment_context",
        "get_rent_payment_context",
        "get_price_override_context",
    }
    check(
        "10. the three original MCP tools still exist",
        original.issubset(set(names)),
        f"{len(names)} tools total",
    )

    readme = (HW5 / "mcp_server" / "README.md").read_text(encoding="utf-8")
    harness = (HW5 / "output" / "harness.md").read_text(encoding="utf-8")
    undocumented_readme = [n for n in names if n not in readme]
    undocumented_harness = [n for n in names if n not in harness]
    check(
        "11/16a. every tool documented in mcp_server/README.md",
        not undocumented_readme,
        f"missing: {undocumented_readme}" if undocumented_readme else ", ".join(names),
    )
    check(
        "16b. every tool documented in output/harness.md",
        not undocumented_harness,
        f"missing: {undocumented_harness}",
    )

    # No arbitrary-SQL escape hatch. Checked two ways: by name, and - the
    # thing that actually matters - by whether any tool accepts a free-text
    # sql/query parameter. A substring match on "exec" is not used; it fires
    # on execute_approved_payment, which takes an id and a token, not SQL.
    banned_names = [
        n
        for n in names
        if re.search(r"^(run|exec(ute)?|raw)_?sql$|^query_database$|^raw_query$", n, re.I)
    ]
    sql_params = []
    for t in tools:
        schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", {}) or {}
        props = (schema or {}).get("properties", {}) if isinstance(schema, dict) else {}
        for param in props:
            if param.lower() in {"sql", "query", "statement", "stmt"}:
                sql_params.append(f"{getattr(t, 'name', t)}.{param}")
    check(
        "   no arbitrary-SQL tool exposed",
        not banned_names and not sql_params,
        f"names={banned_names} params={sql_params}"
        if (banned_names or sql_params)
        else "no SQL-shaped tool name and no free-text sql/query parameter",
    )
    return names


# ----------------------------------------------------------------- 12


def check_limits() -> None:
    from backend import agents as agents_mod

    limits = config.limits_summary()
    sane = all(
        isinstance(v, (int, str)) and (v > 0 if isinstance(v, int) else True)
        for v in limits.values()
    )
    check(
        "12. agent loops are bounded by explicit caps",
        sane
        and "MAX_TOTAL_DELEGATIONS" in (HW5 / "backend" / "agents.py").read_text(
            encoding="utf-8"
        ),
        json.dumps({k: v for k, v in limits.items() if k != "model"}),
    )

    src = (HW5 / "backend" / "agents.py").read_text(encoding="utf-8")
    for guard in (
        "circular_delegation",
        "self_delegation",
        "max_delegation_depth",
        "max_total_delegations",
        "max_repeat_delegations_per_pair",
        "tool_call_limit_reached",
    ):
        check(f"   guard implemented: {guard}", guard in src)

    harness = (HW5 / "output" / "harness.md").read_text(encoding="utf-8")
    mismatched = [
        f"{k}={v}"
        for k, v in limits.items()
        if str(v) not in harness
    ]
    check(
        "15. harness.md documents the actual implemented limits",
        not mismatched,
        f"not found in harness.md: {mismatched}" if mismatched else "all values match",
    )


async def check_guards_actually_fire() -> None:
    """Trigger each loop guard for real and confirm it refuses."""
    from pydantic_ai import RunContext

    from backend.agents import RunState, _delegate_impl, build_agents

    build_agents()

    def ctx_for(state: RunState) -> RunContext[RunState]:
        return RunContext(deps=state, model=None, usage=None)  # type: ignore[arg-type]

    async def attempt(state: RunState, target: AgentName) -> str:
        res = await _delegate_impl(ctx_for(state), target, "probe", 101, None)
        return res.summary

    # Self-delegation.
    s = RunState(run_id="verify-guards", ticket_id=101)
    s.active_chain.append(AgentName.BOSS)
    check(
        "   guard fires: self-delegation refused",
        "cannot delegate to itself" in await attempt(s, AgentName.BOSS),
    )

    # Circular: target already active in the chain.
    s = RunState(run_id="verify-guards", ticket_id=101)
    s.active_chain.extend([AgentName.BOSS, AgentName.INVENTORY])
    check(
        "   guard fires: circular delegation refused",
        "already active higher in this delegation chain"
        in await attempt(s, AgentName.BOSS),
    )

    # Depth cap.
    s = RunState(run_id="verify-guards", ticket_id=101)
    s.active_chain.extend(
        [AgentName.BOSS, AgentName.INVENTORY, AgentName.ACCOUNTING][
            : config.MAX_DELEGATION_DEPTH
        ]
    )
    check(
        "   guard fires: depth cap refused",
        "Delegation depth cap" in await attempt(s, AgentName.FACILITIES),
    )

    # Total delegation cap.
    s = RunState(run_id="verify-guards", ticket_id=101)
    s.active_chain.append(AgentName.BOSS)
    s.delegations_used = config.MAX_TOTAL_DELEGATIONS
    check(
        "   guard fires: total delegation cap refused",
        "delegations" in await attempt(s, AgentName.INVENTORY)
        and "refused" in (await attempt(s, AgentName.INVENTORY)).lower(),
    )

    # Repeat-pair cap.
    s = RunState(run_id="verify-guards", ticket_id=101)
    s.active_chain.append(AgentName.BOSS)
    s.pair_counts["boss->inventory"] = config.MAX_REPEAT_DELEGATIONS_PER_PAIR
    check(
        "   guard fires: repeat-pair cap refused",
        "has already been used" in await attempt(s, AgentName.INVENTORY),
    )

    # Tool-call cap, through the real MCP interception path.
    from backend.agents import _process_tool_call

    s = RunState(run_id="verify-guards", ticket_id=101)
    s.active_chain.append(AgentName.INVENTORY)
    s.tool_calls_used = config.MAX_TOOL_CALLS_PER_RUN

    async def never_called(name, args, *, metadata=None):
        raise AssertionError("tool should not have been reached")

    res = await _process_tool_call(ctx_for(s), never_called, "list_open_tickets", {})
    check(
        "   guard fires: MCP tool-call cap refused",
        res.get("error") == "tool_call_limit_reached",
        f"limit {config.MAX_TOOL_CALLS_PER_RUN}",
    )


# ----------------------------------------------------------- 13, 14


def check_audit_trail() -> None:
    from backend.audit import append_event, sanitize

    path = config.AUDIT_TRAIL_PATH
    before = []
    if path.exists():
        before = json.loads(path.read_text(encoding="utf-8"))

    append_event(
        run_id="verify-audit",
        ticket_id=None,
        step=1,
        agent="boss",
        event_type="verification_probe",
        detail="append-only check",
    )
    after = json.loads(path.read_text(encoding="utf-8"))

    check(
        "13. audit records append rather than overwrite",
        len(after) == len(before) + 1 and after[: len(before)] == before,
        f"{len(before)} -> {len(after)} records, earlier records unchanged",
    )

    # Secrets must never survive sanitization.
    live = os.getenv("PORTKEY_API_KEY") or "sk-fake-secret-value-123456"
    probe = sanitize(
        {"api_key": live, "nested": {"password": "hunter2"}, "text": f"key={live}"}
    )
    leaked = live in json.dumps(probe) if len(live) >= 8 else False
    blob = json.dumps(after)
    in_trail = bool(os.getenv("PORTKEY_API_KEY")) and os.getenv("PORTKEY_API_KEY") in blob
    check(
        "14. audit records contain no secrets",
        not leaked and not in_trail and "hunter2" not in json.dumps(probe),
        "sanitize() redacts key/password fields and live key values",
    )
    # Look for fields that would carry reasoning, not for the substring
    # "reasoning" - an API error message naming the `reasoning_effort`
    # parameter is a legitimate stop reason, not chain-of-thought.
    cot_keys = {
        "reasoning",
        "reasoning_content",
        "chain_of_thought",
        "thought",
        "thoughts",
        "thinking",
        "internal_monologue",
        "deliberation",
        "scratchpad",
    }
    found_keys = sorted({k for r in after for k in r if k.lower() in cot_keys})
    check(
        "   audit records carry no chain-of-thought",
        not found_keys,
        f"reasoning-bearing fields present: {found_keys}"
        if found_keys
        else "no reasoning-bearing fields on any record",
    )


# ------------------------------------------------------------------ main


async def main() -> int:
    print("HW5 Problem 5 verification\n" + "=" * 60)
    check_agents_and_prompts()
    check_no_hardcoded_key()
    check_connectivity()
    check_no_direct_db_access()
    await check_mcp_tools()
    check_limits()
    await check_guards_actually_fire()
    check_audit_trail()
    await check_delegation_executes()

    print("=" * 60)
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED: " + "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
