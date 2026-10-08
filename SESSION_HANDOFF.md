# HW5 — Session handoff note

Context for a fresh Claude Code session. Project root for the homework is `hw5/`;
the Claude Code session itself is normally rooted at `AI Foundations/`.

## Where things stand

- **Problem 1 — done.** `hw5/AI_prompts.md`, 11 sections, Problems 1–4 filled in.
- **Problem 2 — done.** `data/campus_customs_new.db` created as an exact copy of
  `data/campus_customs.db` (original is read-only and must stay untouched).
  Full schema + the three open tickets documented in `output/harness.md`.
- **Problem 3 — done.** FastMCP server at `mcp_server/server.py` with three
  read-only tools. Documented in `output/harness.md` and `mcp_server/README.md`.
- **Problem 4 — in progress.** Config written, connection NOT yet verified.

## Problem 4 — exactly what is left

The MCP config exists at both `.mcp.json` (AI Foundations root) and
`hw5/.mcp.json` (homework evidence copy). Both are identical, valid JSON, with
absolute paths:

```json
{
  "mcpServers": {
    "campus-customs": {
      "command": "C:/Users/geoca/OneDrive/Documentos/MBA/AI Foundations/hw5/.venv/Scripts/python.exe",
      "args": ["C:/Users/geoca/OneDrive/Documentos/MBA/AI Foundations/hw5/mcp_server/server.py"]
    }
  }
}
```

The server itself is verified working: launched over stdio directly, it
handshakes as `campus-customs` (FastMCP 4.0.11) and lists exactly:

- `get_customer_order_fulfillment_context`
- `get_rent_payment_context`
- `get_price_override_context`

What was never confirmed is whether Claude Code itself sees those tools. In the
previous session it did not, because `.mcp.json` was written after that session
had already started.

**First step in the new session:** check the session's connector list for
`campus-customs` and for `mcp__campus-customs__*` tools. Report honestly —
do not claim the connection works unless the tools are actually visible.

Then stop. Roberto will supply one prompt per tool, and those exact prompts must
be recorded as the smoke-test evidence.

## Smoke tests (do NOT run until Roberto gives the prompts)

Evidence goes in `output/mcp_smoke.json`, three records, each with:

1. the exact prompt Roberto gave
2. the exact MCP tool name called
3. the tool output, unaltered

Validate against the database (these are the known-correct values):

- Ticket 101 — `CC-TEE-WHITE`, size S, requested 1, inventory 0, invoice 501,
  vendor Bulldog Print Co
- Ticket 102 — Chapel Street lease, rent $2,400, due 2026-09-02, checking
  balance $3,400, desk date 2026-08-31
- Ticket 103 — `CC-HOOD-NAVY`, size M, requested 20, inventory 8, unit cost $22,
  list price $58

## Standing rules for this homework

- Never modify `data/campus_customs.db` (original) or `data/campus_customs_new.db`
  in Problem 4.
- Do not add MCP tools or rename the existing three.
- Do not work ahead on later HW5 problems.
- Log every prompt Roberto gives into `hw5/AI_prompts.md` under its problem.
- Say "Salve Sodales!" after finishing each task.
- Project `AGENTS.md` rule: address him as Roberto when the current minute is even.

## Environment

- `hw5/.venv` — Python 3.14.7, `fastmcp==4.0.11` (see `hw5/requirements.txt`).
