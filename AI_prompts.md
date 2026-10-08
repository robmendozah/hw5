# AI Prompts Log — Homework 5

Log of the prompts typed to the vibe coder, one section per problem.

## Problem 1 — Vibe coder prompts

### Prompt(s)

```text
Hi Claudius

Problem 1 - Vibe coder prompts

Help me to create the file "AI_prompts.md" that would served as the log of what I will type to my vibe coder.

The log must have 11 sections. Each section must include:

* The problem number and title
* The first prompt I typed
* Additional prompts if needed (only one sentence on what was lacking after the first)

Give me a Salve Sodales! after you are done with each task.
```

### What was lacking

No additional prompt was needed.

## Problem 2 — Study the Campus Customs Database

### Prompt(s)

```text
Let's move forward with Problem 2 — Study the Campus Customs Database.

Work only inside the HW5 project.

1. Preserve the original database: open and inspect data/campus_customs.db, treat it as READ-ONLY, and create an exact working copy at data/campus_customs_new.db. Later homework problems will modify the copy, not the original. Do not rebuild the database manually. After copying, verify the copy exists and can be opened.

2. Inspect the complete database: study every table, and for each one inspect the table name, every field/column, data type where useful, primary key, and foreign keys / obvious relationships. Do not invent relationships that are not supported by the schema.

3. Study the three open tickets: locate them, understand how each links to information in other tables, and identify the relevant IDs or foreign keys. Do not modify or close the tickets.

4. Start the harness: create output/harness.md with a clearly labeled Problem 2 section. For every table, list the table name, list all its fields, and add one short sentence on why that table matters for the agents built later. Briefly mention important relationships, especially those needed to understand the three open tickets.

Constraints: do not modify data/campus_customs.db; do not modify ticket records; use data/campus_customs_new.db as the working copy; do not work ahead on later HW5 problems; preserve existing contents of output/harness.md; base documentation only on the actual schema and records.

After finishing, verify that every database table appears in output/harness.md and that all three open tickets were inspected.
```

### What was lacking

No additional prompt was needed.

## Problem 3 — Build the MCP Server

### Prompt(s)

```text
Let's move forward with Problem 3 — Build the MCP Server.

Continue working inside the HW5 project. Use the database analysis from Problem 2 as the source of truth for the schema and ticket relationships.

Goal: build an MCP server inside mcp_server/ using FastMCP. It should read from data/campus_customs_new.db and must not modify or use the original data/campus_customs.db. For Problem 3 we only need the server and its first three tools — do not connect an agent, do not run the server, do not work ahead.

General tool design: all three tools read only from the working database, never modify it, never invent missing information, return only information supported by the database, use deterministic SQL written inside the tool, do NOT accept arbitrary SQL, return clear structured results, and handle missing or invalid ticket IDs cleanly. Do not hard-code them to tickets 101/102/103 — they must be reusable for other tickets of the same type. Preserve the real relationships: tickets.lease_id -> leases.id, tickets.invoice_id -> invoices.id and invoices.vendor_id -> vendors.id are declared foreign keys, while SKU relationships among tickets, inventory and pricing are value-based joins and must not be described as enforced foreign keys.

Tool 1 — get_customer_order_fulfillment_context(ticket_id): reads tickets, inventory, invoices, vendors; determines whether the requested customer order can be fulfilled and gives the linked invoice/vendor context. Return ticket ID, customer, SKU, size, requested quantity, inventory quantity, whether it can be fulfilled, shortfall, invoice ID and vendor name. Derived fields like can_fulfill and shortfall_quantity are fine when deterministic. Do not invent fulfillment plans, reorder dates or vendor actions.

Tool 2 — get_rent_payment_context(ticket_id): reads tickets, leases, cash_accounts, desk; provides the financial and timing context for a rent notice. Return ticket ID, counterparty, lease ID, property, rent amount, due date, the current operating date from desk, and the cash balance. Deterministic calculations such as days until due, balance after paying rent and whether the balance covers the rent are allowed using only database values. Do not decide whether to pay or execute any payment.

Tool 3 — get_price_override_context(ticket_id): reads tickets, inventory, pricing; provides the operational and pricing facts for a price-override request. Return ticket ID, customer, SKU, size, requested quantity, inventory quantity, shortfall, unit cost and list price. Clearly label any pricing-derived calculations as based only on database fields. Do NOT invent an approved override price, a maximum discount, a pricing policy or a required margin threshold.

Use FastMCP in the simplest clear structure. Keep tool names and descriptions explicit. Do not create generic tools such as run_sql, query_database or get_data — expose clear business capabilities, not unrestricted database access.

Update output/harness.md, preserving the Problem 2 content, with a Problem 3 section listing all three tools: tool name, the tables it reads, which ticket it unlocks (101/102/103), and one specific sentence connecting the tool to that ticket's business question. Note where a relationship is a value-based join rather than a declared foreign key.

Create a short mcp_server/README.md explaining what the server is for, which database it uses, that the tools are read-only at this stage, and one concise sentence per tool; mention that later problems may add more tools.

Then verify: the server points to campus_customs_new.db, the original is untouched, all three tools exist with the exact names, the tools are read-only, no tool exposes arbitrary SQL, each ticket's tool uses the real relationships, SKU matches are treated as value-based joins, missing values are returned honestly, and both documents are accurate. Do not connect or run the MCP server in this problem.
```

### What was lacking

No additional prompt was needed.

## Problem 4 — Add the MCP Server to the Vibe Coder and Test Each Tool

### Prompt(s)

```text
Let's move forward with Problem 4 — Add the MCP Server to the Vibe Coder and Test Each Tool.

Continue working inside the existing HW5 project. The MCP server from Problem 3 already exists under mcp_server/ and uses data/campus_customs_new.db. First connect that local MCP server to my vibe coder so it can call the three MCP tools.

Step 1 — Configure the MCP connection: inspect the project and the MCP configuration format expected by the vibe coder I am using; do not invent a configuration schema if a standard local MCP-server format already exists. Save the local MCP connection configuration in .mcp.json at the project root, unless the vibe coder requires another standard location — if so, still preserve the connection JSON text in .mcp.json as homework evidence. The configuration must use the correct local command/entry point for the FastMCP server, valid project paths, no secrets, and must point the server at data/campus_customs_new.db. The three tools that must become available are get_customer_order_fulfillment_context, get_rent_payment_context and get_price_override_context.

Step 2 — Verify the connection only: confirm the vibe coder can see the MCP server and the three tool names. Do NOT run the three smoke tests yet. Do not fabricate a successful connection. If a restart, reload, reconnect or manual approval is required, tell me exactly what to do. Only tell me the connection is working if the tools are actually visible to the vibe coder. Then stop and wait — I will give one prompt per tool so the evidence reflects my exact prompts.

Step 3 — Smoke-test evidence structure (for later): save evidence in output/mcp_smoke.json with, for each of the three tools, the exact prompt I gave, the exact MCP tool name called, and the tool output. Output must reflect actual values from data/campus_customs_new.db; do not clean up outputs in a way that changes values and do not invent missing values.

Validation requirement: check returned values against the database — ticket 101 (CC-TEE-WHITE, size S, qty 1, inventory 0, invoice 501, vendor Bulldog Print Co), ticket 102 (Chapel St lease, rent $2,400, due 2026-09-02, checking $3,400, desk date 2026-08-31), ticket 103 (CC-HOOD-NAVY, size M, qty 20, inventory 8, unit cost $22, list price $58). Use these only as validation; the tools must still read from campus_customs_new.db.

Constraints: do not modify either database; do not add new MCP tools; do not change the three tool names; do not work ahead; do not run the smoke tests until I provide the prompts; do not claim the connection works unless the vibe coder actually sees the tools.

Proceed with MCP configuration and connection verification only, then stop and wait for my test prompts.
```

### What was lacking

The first prompt could not be completed in one session: `.mcp.json` was written after that Claude Code session had already started, so the server was not loaded and the tools were not visible; a fresh session was required to pick up the project MCP config.

### Additional prompt(s)

```text
Continuing HW5 Problem 4. Read hw5/SESSION_HANDOFF.md first, then check whether the campus-customs MCP server is connected and its three tools are visible. Do not run the smoke tests yet.
```

Result: in the new session the connector list reports `campus-customs` as kind `project`, transport `stdio`, status `connected`, `tool_count: 3`, and all three tools are exposed as `mcp__campus-customs__get_customer_order_fulfillment_context`, `mcp__campus-customs__get_rent_payment_context` and `mcp__campus-customs__get_price_override_context`. Smoke tests not run; awaiting one prompt per tool.

#### Smoke test 1 of 3 — ticket 101

```text
Investigate open Ticket 101 using the MCP tools available in this project. Determine whether the customer order can currently be fulfilled, and report the linked invoice and vendor context. Use the appropriate MCP tool and return only information grounded in data/campus_customs_new.db.
```

Tool called: `mcp__campus-customs__get_customer_order_fulfillment_context` with `ticket_id: 101`. Result: `can_fulfill: false`, shortfall 1 unit of `CC-TEE-WHITE` size S (inventory 0), linked to open invoice 501 ($840, due 2026-08-28) from vendor Bulldog Print Co. All six validation values matched. Unaltered output saved to `output/mcp_smoke.json`.

#### Smoke test 2 of 3 — ticket 102

```text
Investigate open Ticket 102 using the MCP tools available in this project. Summarize the rent obligation, due date, current operating date, and available checking balance, and state whether the current balance is sufficient to cover the rent. Use the appropriate MCP tool and return only information grounded in data/campus_customs_new.db.
```

Tool called: `mcp__campus-customs__get_rent_payment_context` with `ticket_id: 102`. Result: Chapel Street shop lease, rent $2,400 due 2026-09-02, operating date 2026-08-31 (2 days until due), checking balance $3,400, `balance_covers_rent: true` leaving $1,000. All six validation values matched. Unaltered output saved to `output/mcp_smoke.json`.

#### Smoke test 3 of 3 — ticket 103

```text
Investigate open Ticket 103 using the MCP tools available in this project. Report the requested SKU, size, quantity, current inventory, unit cost, and list price, and identify any inventory shortfall. Use the appropriate MCP tool and return only information grounded in data/campus_customs_new.db. Do not invent an override price or discount policy.
```

Tool called: `mcp__campus-customs__get_price_override_context` with `ticket_id: 103`. Result: `CC-HOOD-NAVY` size M, requested 20 vs inventory 8, shortfall 12; unit cost $22, list price $58 ($36/unit list margin, 62.07%). The tool reports the database holds no approved override price, discount cap or margin threshold, so none was proposed. All six validation values matched. Unaltered output saved to `output/mcp_smoke.json`.

All three Problem 4 smoke tests complete: three distinct MCP tools, three tickets, all validation values matched, both databases unmodified.

## Problem 5 — Build the Agent Team and Grow the MCP Tools

### Prompt(s)

```text
Let's move forward with Problem 5 — Build the Agent Team and Grow the MCP Tools.

Continue working inside the existing HW5 project. Preserve the MCP server and tools created in Problems 3-4.

Goal: build the Campus Customs agentic team using PydanticAI — Boss, Inventory, Accounting, Facilities, Customer Service — with FULL CONNECTIVITY: any agent may delegate a focused task to any other agent; delegation must actually work in code, not exist only as language in the system prompts; agents may collaborate across functions when a ticket requires multiple specialties. All five agents must use PORTKEY_API_KEY and only gpt-6-luna. Do not hard-code the API key.

Architecture: agent code under backend/, one system-prompt file per agent under backend/prompts/, shared Pydantic data types in backend/models.py.

Critical data-access rule: all Campus Customs shop facts must come through the MCP server, which reads data/campus_customs_new.db. Do not create a second shop-data layer inside backend/. Agents must NOT open SQLite directly, use sqlite3, recreate the MCP SQL logic in agent files, or invent database values. The architecture is Agent -> MCP tool -> campus_customs_new.db -> structured result -> agent reasoning.

Preserve the existing three tools. Before adding new tools, inspect what information the five agents need for Tickets 101, 102 and 103, and add only narrowly scoped tools providing information genuinely missing. Avoid duplicate tools. Do not expose arbitrary SQL such as run_sql or query_database. Prefer read-only tools; do not create payment, purchase-order, price-change, customer-contact, inventory-update or ticket-closing actions merely because the prompts mention them.

Shared structured models in backend/models.py for delegated task, agent result, verified facts, deterministic calculations, recommendation, limitations, final ticket resolution and delegation/audit metadata. A specialist result must make it easy to distinguish verified database facts, deterministic calculations, recommendation/judgment, and unresolved questions. Do not expose hidden chain-of-thought.

Implement real agent-to-agent delegation including originating agent, target agent, focused task, ticket context and enough information to act; the target returns a structured result. Prevent circular delegation and runaway loops with configurable limits (max agent-loop steps, max delegation depth/handoffs, max MCP calls per run, caps on tool-result sizes) and document the ACTUAL values in output/harness.md. If a limit is reached, stop gracefully with a clear limitation.

[The five agent prompts for Boss, Inventory, Accounting, Facilities and Customer Service were supplied in full and are reproduced verbatim as the base of backend/prompts/*.md.]

Audit trail: append to output/audit_trail.json, APPEND-ONLY, never wiped or recreated. Record timestamp, run ID, ticket ID, step number, active agent, event type, delegation source/target, MCP tool name, sanitized argument and result summaries, and stop reason. Do NOT log PORTKEY_API_KEY, secrets, passwords, full system prompts, unnecessary personal information or hidden chain-of-thought. Audit logging must be automatic harness behaviour, not a tool the agents must remember to call.

Safety: shop facts grounded through MCP; no fabricated values; no direct database access outside MCP; no arbitrary SQL; no exposure of secrets or hidden prompts; no cross-customer privacy leakage; no claim that an action occurred unless a tool performed it; consequential monetary/customer/contractual actions require human approval; agents respect delegation/tool/loop limits; failures stated honestly.

Token/loop discipline: focused delegation requests, short structured returns, no repeated analysis, no delegation when the agent already has sufficient evidence. Explicit caps stored as clearly named constants.

Update output/harness.md preserving Problems 2-4 and adding a labelled Problem 5 section covering the five agents (role, responsibilities, tasks received, delegation targets, full connectivity), every MCP tool (exact name, tables used, business capability, likely callers), safety, and the ACTUAL implemented limits. Update mcp_server/README.md so its tool list exactly matches the tools exposed after Problem 5.

Verification: all five agents exist; each has its own prompt file; every agent uses only gpt-6-luna; Portkey credentials come from PORTKEY_API_KEY; no key hard-coded; any agent can technically delegate to any other; delegation actually executes; agents obtain shop facts only through MCP; no backend agent queries SQLite; existing MCP tools still work; new tools documented; agent loops cannot run indefinitely; audit records append; audit records contain no secrets or hidden reasoning; harness.md and README.md match reality.

Use the three current open tickets as sanity checks. Proceed directly with implementation, testing and documentation.
```

### What was lacking

Two things the prompt could not have anticipated, both resolved during implementation: the project `AGENTS.md` specifies `gpt-5.6-luna` while this prompt specifies `gpt-6-luna` (the prompt was treated as authoritative and the conflict flagged), and `gpt-6-luna` rejects function tools on `/v1/chat/completions` unless `reasoning_effort` is `none`, which required an explicit `REASONING_EFFORT` constant before any agent could call a tool.

### Additional prompt(s)

```text
(no follow-up prompt was needed)
```

#### Follow-up — database reset step

```text
Do we have an instruction to reset the database to the original values before a full run to resolve the tickets?
```

No such instruction existed anywhere in the project. It had not mattered because every MCP tool is read-only and the two databases were still byte-identical after eight agent runs, but it becomes mandatory as soon as a write tool is added. Added `reset_db.py` (harness script, not an MCP tool, so agents cannot erase evidence of their own writes) with baseline-hash refusal, post-copy verification and a `database_reset` audit record. Documented in `output/harness.md`.

#### Outcome

Five PydanticAI agents under `backend/` with full any-to-any delegation (20 ordered pairs, all live in code). Five new read-only MCP tools added alongside the original three: `list_open_tickets`, `get_product_availability`, `get_cash_position`, `get_vendor_directory`, `get_payment_history`. All three tickets ran end-to-end against gpt-6-luna through Portkey, with real nested delegation (ticket 101 reached depth 2: Boss -> Customer Service -> Inventory). `verify_problem5.py` runs 33 checks covering all sixteen assignment requirements and passes, including executable proof that delegation runs the target agent and that all six loop guards actually refuse rather than merely existing in source.

## Problem 6 — Plan the Three Tickets

### Prompt(s)

```text
Let's move forward with Problem 6 — Plan the Three Tickets.

Continue working inside the existing HW5 project. This problem is a PLANNING problem. Before we run the agents to resolve the tickets, I want to document what I expect the agent team to do. Do NOT resolve the tickets and do NOT modify the working database as part of creating the plan.

Goal: build output/desk_tickets.html, a standalone HTML page openable by double-click, with one tab per open ticket (101, 102, 103) plus Cash and Reflection tabs left as "Coming later" placeholders.

On each ticket tab, two clearly labeled sections: Expected (filled now) and Actual (left empty, marked "To be completed after the agent run"). Do not invent Actual results. Each Expected section must document which agent the Boss should call FIRST and why, the sequence of specialist delegations expected after that, which MCP tools the run should use, and the business constraints affecting that ticket. Do NOT simply write "Boss calls everyone" — the plan must show a purposeful workflow where agents are called because their expertise is actually needed. Use the actual MCP tool names currently implemented.

If the plan reveals a genuinely missing MCP capability needed to enforce a shop rule or retrieve required data, add the narrowest appropriate MCP tool and update output/harness.md and mcp_server/README.md. Do not create duplicate tools.

Ten authoritative shop rules were supplied governing desk.date_today as "today", vendor lead times from the vendors table, vendors not shipping while holding an open unpaid invoice, human approval before any payment, point deductions for unapproved payment, database updates when payment is made, payment-tool refusal on insufficient cash with balances never negative, cash flowing only OUT with no revenue modeled, resetting the working database before the later full run, and no emailing customers or calling real vendors.

Document all ten in a "Shop Rules / Operating Constraints" section of output/harness.md, and enforce them in the appropriate places: agent prompts should know the rules affecting their role; MCP/action tools should enforce hard constraints where possible; the payment tool should refuse insufficient-cash payments rather than relying on Accounting to remember; human approval must be checked before any payment tool executes; Customer Service must remain draft-only; the database-reset requirement belongs in the run/test workflow rather than agent reasoning. Do not rely on prompt text alone for hard financial controls that can be enforced deterministically in code.

[Detailed expected workflows were supplied for all three tickets: 101 Boss→Inventory first (fulfillment problem, quantify shortfall, vendor lead time, vendor unpaid-invoice block, delegate to Accounting for the payment constraint, then Customer Service draft, no sale proceeds added to cash); 102 Boss→Facilities first (Facilities owns leases; rent due 2026-09-02 approaching but not overdue on desk date 2026-08-31; delegate to Accounting for capacity, approval before payment, Inventory and Customer Service not involved); 103 Boss→Accounting first (explicitly a pricing question; Customer Service must not set pricing; delegate to Inventory for the 12-unit shortfall and vendor block; invent no discount percentage or margin rule; escalate if policy is absent; prefer get_price_override_context over get_customer_order_fulfillment_context).]

HTML presentation: make the page easy to read and grade, each tab showing ticket title/type, key facts, expected workflow, Boss first call, expected delegation sequence, expected MCP tools, relevant shop rules, and an empty Actual section. Keep the HTML standalone with internal styling only.

Do NOT reset or modify the database as part of this planning problem, but include a visible note in the planning/harness documentation that the working database must be restored from the original before the later full run.

Proceed directly with the planning HTML, shop-rule documentation, and any narrowly necessary MCP read capability discovered during planning.
```

### What was lacking

The prompt asked for hard financial controls to be enforced in code rather than prompt text, but rules 4-7 all describe a payment tool that does not exist yet and that a read-only planning problem must not create — so those four rules are documented with an explicit, labelled enforcement gap rather than being claimed as enforced.

### Additional prompt(s)

```text
(no follow-up prompt was needed)
```

#### Outcome

Built `output/desk_tickets.html` (standalone, five tabs, three Expected plans filled, three Actual sections left empty, Cash and Reflection placeholders). Added one MCP tool, `get_vendor_shipping_status(vendor_id)`, which evaluates shop rule 3 deterministically instead of leaving an agent to cross-reference `get_cash_position` and `get_vendor_directory`. Appended role-specific shop rules to all five agent prompts. Documented all ten rules in `output/harness.md` with a per-rule enforcement column, the rules 4-7 gap, and the reset reminder. Database unmodified; verification 33/33.

## Problem 7 — Backend Routes

### Prompt(s)

```text
Let's move forward with Problem 7 — Backend Routes.

Continue working inside the existing HW5 project. Preserve the agent team, MCP server, audit trail, shop rules, safety controls, and database architecture from the previous problems.

Goal: the React dashboard in the next problem needs a FastAPI backend exposing the Campus Customs agent system and current shop state through clear API routes. Implement the FastAPI application in backend/main.py, keeping main.py primarily as the HTTP/API layer. Do not duplicate agent reasoning, MCP database logic, or business rules inside route handlers when those capabilities already exist elsewhere. The intended architecture is React dashboard -> FastAPI routes -> agent team / controlled application logic -> MCP server -> data/campus_customs_new.db.

Six required capabilities: (1) GET /tickets returning tickets 101-103 and their current status including whether open or resolved, from actual database values, not hard-coded. (2) POST /tickets/{ticket_id}/run which validates the ticket exists, invokes the existing agent-team workflow, lets Boss and specialists collaborate through the existing agent/MCP architecture, returns a structured result, rejects unknown ticket IDs cleanly, and must not bypass human-approval rules or reimplement ticket-solving logic in main.py. (3) GET /events returning recent agent activity from the append-only output/audit_trail.json with timestamp, ticket ID, active agent, event type, delegation source/target, MCP tool, sanitized result summary and stop reason, excluding keys, passwords, hidden prompts and chain-of-thought, with a documented result cap. (4) A human-approval route such as POST /approvals/{approval_id}/approve. CRITICAL: the frontend must NOT be able to send an arbitrary amount and have it subtracted from cash. Agents prepare a specific proposed action with trusted details; the approval route receives an identifier, retrieves authoritative details, validates, and only then executes. Enforce human approval, sufficient cash, never-negative balances, vendor/payment constraints and database updates after success. Human approval does not override insufficient-cash safeguards. Prevent double execution. On invalid or already-executed approvals return a clear error and do not partially modify the database. Agents only PREPARE; this route authorizes and triggers the mutation. (5) GET /cash returning the current checking balance from the actual cash_accounts table. (6) POST /reset restoring campus_customs_new.db from the pristine campus_customs.db, which must remain unchanged — and resetting must NOT wipe output/audit_trail.json; append a sanitized reset event instead.

Use or extend backend/models.py for request/response contracts, reusing existing compatible models rather than duplicating representations. Configure only the minimal CORS needed for local Vite development. Return clear HTTP errors for ticket not found, malformed request, approval not found, approval already executed, insufficient cash, MCP/tool failure, agent execution failure and reset failure, without exposing stack traces or secrets. The backend must run from inside backend/ with uvicorn main:app --reload --port 8000, available at http://localhost:8000 with docs at /docs.

Update output/harness.md with a labelled Problem 7 section listing each implemented route in one line (method, URL, what it does) using actual route names, and document route-level limits such as the number of recent events returned.

Verify all fourteen points: tickets route returns 101-103 with actual statuses; invalid ticket ID rejected; run route invokes the existing agent team; events returned from the audit trail; approval route cannot execute an arbitrary frontend-provided amount; human approval required before payment; insufficient-cash transactions refused; approved action cannot execute twice; successful financial action updates the database; cash route returns the actual balance; reset restores the database; reset does not erase audit_trail.json; agent/MCP safety rules intact; harness.md lists all actual routes.

Do not build the React dashboard yet. Proceed directly with implementation, API testing, and harness documentation.
```

### What was lacking

The prompt specified the prepare-then-approve flow but not where the money-moving code should live. The design decision taken was to make execution an MCP tool gated by a one-time token minted only by the approval route, which keeps every database mutation inside the established MCP layer while leaving it structurally unreachable by any agent.

### Additional prompt(s)

```text
(no follow-up prompt was needed)
```

#### Outcome

`backend/main.py` implements nine routes with no SQL, no business rules and no ticket logic. Two MCP tools were added: `prepare_payment_proposal` (callable by agents, moves no money, fixes the amount from the database) and `execute_approved_payment` (the only write tool, token-gated, atomic, refuses insufficient cash regardless of approval). A shared `proposal_store.py` holds proposals and mints one-time execution tokens. `test_api.py` passes 28/28 against a live server, covering all fourteen verification points — including posting `amount: 999999` against an $840 proposal and observing $840 execute. Two stale heuristics in `verify_problem5.py` produced false positives once Problem 7 landed and were corrected; it passes 33/33.

## Problem 8 — Agent Dashboard

### Prompt(s)

```text
Let's move forward with Problem 8 — Agent Dashboard.

Continue working inside the existing HW5 project. Preserve the FastAPI backend, agent team, MCP server, audit trail, approval controls, database-reset behavior, and shop rules from Problems 3-7.

Goal: build the frontend dashboard in frontend/ using React, Vite and TypeScript. It should be the human operations desk for the Campus Customs agent team and must call the FastAPI routes from Problem 7 rather than duplicating backend logic. Architecture: React dashboard -> FastAPI at http://localhost:8000 -> agent team / approval logic -> MCP server -> campus_customs_new.db. The frontend must NOT query SQLite directly, calculate authoritative cash values itself, execute payments itself, mark tickets resolved without backend confirmation, invent agent events, or simulate successful approvals the backend did not execute. Allow http://localhost:5173 through CORS narrowly, and preserve a configurable API base URL rather than hard-coding URLs.

Required functionality: list tickets 101-103; show each ticket's status (open, running, awaiting approval, resolved, error); let me select a ticket; start the agent team on it; show each agent and what they are doing while it runs; refresh recent agent events; update ticket status when the backend reports the run finished; summarize what each agent contributed; show any proposed payment requiring approval; let a human approve it; refresh approval status, ticket status, events and balance after approval; and show the checking balance prominently. The balance changes only when the backend confirms a payment changed the database. Use clear UI states (OPEN -> RUNNING -> AWAITING APPROVAL -> RESOLVED), never marking a ticket resolved because an animation finished, polling only while a run is active, and showing a clear error state on failure.

Creative concept: "Campus Customs Regional Operations Office" — a strong personality inspired by the mundane regional-office / mockumentary workplace feeling, without copying branded graphics, characters, logos or props. The humour should come from five sophisticated AI agents coordinating through a dashboard that feels like an extremely ordinary late-2000s local office: beige partitions, manila folders, metal filing cabinets, corkboard, sticky notes, laminated badges, an accounting ledger, inbox/outbox trays, a whiteboard, rubber approval stamps, institutional blue/green, paper clips and tab dividers, subtle fluorescent atmosphere. Polished and intentional rather than messy.

[A full desktop layout sketch was supplied — masthead with cash and reset, INBOX of manila folders, centre ACTIVE CASE FILE, right STAFF ROOM roster, a wide LIVE OFFICE FEED, and a bottom row of APPROVAL TRAY and CASE NOTES — together with detailed direction for each region: colour-coded folder tabs by status, the selected folder pulled from the stack, an [ASSIGN TEAM] control becoming "TEAM AT WORK…", five agent nameplates with role, status glyph and restrained colour accents, an activity log distinguishing speech, MCP tool stamps, outcomes, approvals and errors without exposing chain-of-thought, a red-bordered NEEDS SIGNATURE document with a stamp animation only after backend confirmation, a clipped agent memo, resolved tickets retained with a stamp, and an accounting-ledger cash card that must not look like a trading terminal. A specific palette was given (paper #F2EAD7, manila #D8B77A, institutional blue #54728A, muted office green #72856A, accounting green #426A4A, stamp red #A04444, charcoal #303437, desk brown #735E48, off-white #FAF8F2), with 2-3 font families, subtle physical motion respecting prefers-reduced-motion, and responsive stacking on narrow screens.]

Create or update output/design.md explaining the concept, the mockumentary inspiration, why tickets look like manila folders, why agents appear as coworkers, how the feed makes multi-agent work understandable, why proposals appear in a Needs Signature tray, how cash is presented as a ledger, how resolved tickets and contributions are represented, and why the design makes the system easier and more enjoyable to operate.

Verify by starting both servers and confirming all three tickets display, selecting each, running one, seeing real agent activity and events, correct participating agents, a completed ticket updating visually, approval required for financial actions, approval going through the backend without client-side cash mutation, cash refreshing after payment, errors not breaking the interface, usability at a narrow viewport, and design.md reflecting the final design.

Do not change backend business rules merely to make the dashboard easier to implement. Proceed directly with implementation, integration testing, and design documentation.
```

### What was lacking

The prompt specified a detailed manila/institutional office palette, which conflicts with the project `AGENTS.md` rule that web apps use a black-and-green visual style; the Problem 8 palette was treated as the more specific and deliberate instruction, and the conflict was flagged rather than silently resolved.

### Additional prompt(s)

```text
(no follow-up prompt was needed)
```

#### Outcome

Built `frontend/` (React + Vite + TypeScript) as a physical operations desk. All fifteen verification points were exercised against both live servers: a real ticket-101 run drove the folder through Open → Running → recommendation, the roster correctly left Accounting and Facilities idle because they did not participate, approving a prepared proposal moved cash $3,400 → $2,560 only after backend confirmation, a second rent approval at $160 was refused with the backend's own message and **no stamp appeared**, stopping the backend produced a clean "Office system temporarily unavailable" card that recovered without a reload, and 375px showed no horizontal overflow. `output/design.md` covers all nine required points plus one honest limitation: run outcomes live in browser state, so the Case Notes memo clears on reload.

#### Follow-up — making human approval intuitive

```text
But for example for the Ticket 102 there is no need of a response of any customer. So you should expect an approval from the User (Human). Or maybe the way of approval is not clear, could you help me to modify the app to make the Human approval of payment more intuitive?
```

A correct observation. On a live ticket-102 run Accounting checked the rent context and the cash position, recommended approval, and never called `prepare_payment_proposal` — so the operator was left with a recommendation and nothing to sign. Four changes: a deterministic `POST /tickets/{id}/prepare-payment` route taking only a ticket id (obligation and amount still resolved from the database, signature still required); the pending request rendered inline on the case file via a shared `ApprovalCard`, driven by the proposal list so it survives a reload; a red masthead badge counting waiting signatures and scrolling to the request; and a strengthened Accounting prompt. The prompt change is explicitly treated as the weakest of the four — the agent still did not prepare in the run tested afterwards, which is exactly why the deterministic path exists. Verified end to end in the browser: the fallback button produced a $2,400 request, and approving from the case file moved cash $3,400 → $1,000, with the stamp landing only after backend confirmation.

#### Follow-up — shop rule 11 (low-value auto-restock) and the $840 question

```text
Also maybe for small inventory orders, especially when inventory is 0, it could be purchased in advance regardless that the customer has not confirm the order.

Also, could you explain me why the payment is 840 if Tauhid is ordering only 1 piece?
```

**On the $840.** It is not the price of Tauhid's shirt. `CC-TEE-WHITE` has `unit_cost` $8.00 and `list_price` $28.00; the $840 is invoice 501, a pre-existing debt to Bulldog Print Co for a "Rush reprint CC-TEE-WHITE S" that came due 2026-08-28 — three days before ticket 101 was created. The two are joined only by `tickets.invoice_id = 501`, and the invoice matters because shop rule 3 freezes the vendor until it is paid. It is a gate, not a price. (At $8/unit the figure is consistent with ~105 units, but `invoices` has no quantity column, so the database does not actually say.)

**On buying ahead.** Implemented as shop rule 11 after the operator chose the low-value auto-restock option. New MCP tool `prepare_stock_purchase(sku, size, quantity, ticket_id)` prepares a restock for human approval; the bounds are enforced in the tool rather than by prompt — a hard `STOCK_PURCHASE_CAP_USD = 100.0` cap, a refusal when the inferred supplier has an open unpaid invoice, and an amount computed as `quantity × pricing.unit_cost`. Execution increments inventory in the same transaction as the cash deduction. Verified: 12 × CC-HOOD-NAVY ($264) refused above cap; 1 × CC-TEE-WHITE refused while invoice 501 is open; 5 × CC-MUG-CREST at $17.50 approved, cash $3,400.00 → $3,382.50 and stock 0 → 5. Two limitations documented honestly: the schema has no vendor-to-SKU mapping (so a supplier is often not identifiable), and `payments` has no item columns. Note the rule changes nothing for ticket 101 — vendor 1 stays blocked until the $840 is settled.

#### Follow-up — pixel-art staff sprites

```text
I want to see some HTML representation of the agents working, maybe with a little movement. Could you help me with that. Maybe something like a pixels drawings.
```

Added `PixelAgent.tsx`: a 16x16 pixel figure per agent, drawn as SVG rects with `shape-rendering: crispEdges`, seated at a desk in that agent's colour. Two frames, and the backend-reported status decides the animation — working types with a warm desk lamp, delegated drifts a token to the right, waiting types at half speed, done rests with a tick, idle dims and blinks. Still frames under `prefers-reduced-motion`. This relaxes the Problem 8 "no cartoon avatars" rule, which was flagged before implementing.

Testing the sprites surfaced a real bug that had nothing to do with the artwork: live runs now finish in 2-5 seconds, but events polled every 3 seconds, so the Staff Room usually showed no activity at all — and worse, `staffStatuses` derived status from *every* event for a ticket, mixing in earlier runs and showing staff "working" who had finished minutes before. Fixed by scoping the roster to the newest `run_id` for that ticket and shortening the poll to 1.2s with an immediate first refresh. Verified by sampling the DOM during a live run: the Inventory sprite flips to `px--working` mid-run and back to `done`.

## Problem 9 — Resolve the Tickets

### Prompt(s)

```text
Let's move forward with Problem 9 — Resolve the Tickets.

This problem is the FULL REAL RUN of Tickets 101, 102 and 103 using the actual agent team, MCP tools, FastAPI backend, React dashboard, human-approval flow, working database and audit trail. Do not simulate results or fill deliverables from the Expected plan.

Reset data/campus_customs_new.db to the original before running anything and verify the reset succeeded; do not reset again between tickets, so the three run sequentially against the same evolving database. Do NOT erase output/audit_trail.json — it stays append-only — and record an audit event for the reset if the architecture supports it. Immediately after the reset and before any ticket, read and record the actual checking balance from cash_accounts rather than assuming it.

Run 101, 102 then 103 through the real architecture: start the agent team, allow real Boss/specialist delegation and real MCP calls, capture actual events in the audit trail, and if an action requires human approval STOP and wait for me to approve through the dashboard — do not simulate, forge or programmatically bypass it. Continue until the backend/database reports the ticket resolved, recording the checking balance and any payments after each. Do not mark a ticket resolved in documentation unless the actual database status is resolved. For any approval tell me the ticket, proposed action, dollar amount and what to click, then wait.

Produce an exact cash reconciliation from actual database records: starting balance, each ticket's real movements with invoice/vendor/obligation and amount, and the resulting balance, ending at a figure that matches cash_accounts exactly. Cash only goes OUT; customer revenue is not modeled. Investigate rather than adjusting records if the arithmetic does not reconcile.

Fill the Actual sections of output/desk_tickets.html (preserving the Problem 6 Expected sections) with final status, participating agents, the Boss's first delegation, actual delegations, MCP tools used, verified facts, human approvals, executed financial actions and outcome — based only on real evidence. Complete the Cash tab with the itemised reconciliation, saying explicitly where no cash moved. Create output/resolved_tickets.json with structured per-ticket evidence. Capture real dashboard screenshots per resolved ticket into output/resolved_board_images/ and build a standalone output/resolved_board.html referencing them with relative paths. Keep appending to audit_trail.json without wiping it, logging no secrets or chain-of-thought. Finish output/harness.md so it documents the actual final system: database, MCP tools, agent team, backend routes, dashboard, and safety/business controls.

Verify seventeen points before declaring completion. Do not modify results to make Expected and Actual match — differences are useful evidence and should remain visible.
```

### What was lacking

The prompt assumed tickets could reach a `resolved` status in the database, but Problem 5 had deliberately built no ticket-closing action, so `tickets.status` had no write path at all. Raised before running anything rather than discovered at the deliverable stage; the operator chose "agents request, humans confirm", which was then implemented.

### Additional prompt(s)

```text
Ok run the app, and run the three tickets in order. Im gonna let you know when I approved things for you to screenshot the page and update or create the resolved_board.html
```

```text
Approved
```

```text
I also marked as resolved the first ticket
```

```text
I approved the rent and marked both the ticket 2 as resolved. Make sure to take screenshots for the html.
```

```text
Now I resolved ticket 103 for you to capture the screenshot
```

#### Outcome

All three tickets resolved in the database with an exact cash reconciliation: **$3,400.00 − $840.00 (invoice 501) − $2,400.00 (rent) − $0.00 = $160.00**, matching `cash_accounts` exactly. Both payments carry `approved_by = "Front Desk"`; every approval and every closure was performed by the operator through the dashboard — none were bypassed in code. 19/19 final verification checks pass, and `verify_problem5.py` still passes 33/33 (it caught two undocumented tools during this problem).

Two things worth recording. First, the resolution gap above: resolved by adding `request_ticket_resolution` (agents ask) and `confirm_ticket_resolution` (token-gated, human-only), preserving the control model used for payments. Second, a genuine defect — the first run of ticket 103 lost its Inventory delegation to a transient Windows file lock during an audit write (`WinError 5`, OneDrive holding the file open). The system degraded honestly rather than crashing, the three JSON writers now retry with backoff, and the re-run went from 3 agents with an error to 4 agents and 19 clean steps. Both attempts remain in the audit trail.

Plan-versus-run differences were left visible rather than reconciled: on 103 the Boss opened with Inventory rather than Accounting and fanned out to three specialists instead of running a chain, and across all three tickets the agents recommended payments without preparing them.


### Prompt(s)

```text
(first prompt goes here)
```

### What was lacking

(one sentence on what the first prompt did not cover, or "No additional prompt was needed.")

### Additional prompt(s)

```text
(follow-up prompt goes here, if any)
```

## Problem 10 — Reflection

### Prompt(s)

```text
Let's move forward with Problem 10 — Reflection.

Open output/desk_tickets.html and update ONLY the Reflection tab. I do NOT want you to write the reflection for me. I want a clean template that I can fill in myself after reviewing the Actual results. Preserve all existing tabs and content.

Create five sections: (1) Evaluation of performance, with a subsection per ticket asking what the agents did well, what was inefficient/incomplete/unnecessary, whether the underlying business problem was actually solved or the ticket only administratively closed, whether the agents respected the data/approval/safety/non-hallucination rules, and an overall evaluation or score. (2) Actual vs Expected, with a per-ticket comparison template covering what matched the Expected plan, what differed, whether the difference was better/worse/simply a different valid orchestration path, tools planned but not used, and unplanned tools or delegations that proved useful. (3) What would have been simpler with ONE agent + tools, per ticket, asking whether one agent with the existing tools could have solved it more simply, why or why not, what coordination overhead the multi-agent system added, what value specialization added, and a final conclusion. (4) Three problems this team could crush, as numbered placeholders each with problem description, why the current team could solve it, which agents would participate and which current MCP tools would be used. (5) Three problems that would exceed the current team, each with problem description, why the team cannot solve it, what data/policy/capability is missing, what new MCP tools would be needed and which existing or new agents would use them.

Add a final blank box titled "Main lesson from the experiment".

Keep the existing style of desk_tickets.html. Make the Reflection tab visually clean and easy to fill in, using clear headings, short guiding questions, blank text areas / placeholder boxes and comparison tables where useful. Do not write the reflection for me. Do not summarize the Actual results inside the Reflection tab. Only create the template and guiding questions. Proceed directly with updating the Reflection tab only.
```

### What was lacking

Nothing — the brief was specific about scope and about what not to do. The only judgement call was making the write-in boxes `contenteditable` with `localStorage` persistence, so the template is usable in the browser as well as by editing the HTML source.

### Additional prompt(s)

```text
(no follow-up prompt was needed)
```

#### Outcome

Reflection tab rebuilt as a blank template: five sections plus the final takeaway box, **73 write-in boxes, every one empty**, with ruled-paper styling matching the rest of the page. Section 2 uses comparison tables (question left, blank answer cell right); sections 4 and 5 use numbered problem cards. Typed answers persist in `localStorage` and paste as plain text so the ruling stays intact. Verified in the browser: all five tabs intact, the three Expected sections and three Actual sections untouched, the Cash tab unchanged, and no answer text anywhere in the tab.


### Prompt(s)

```text
(first prompt goes here)
```

### What was lacking

(one sentence on what the first prompt did not cover, or "No additional prompt was needed.")

### Additional prompt(s)

```text
(follow-up prompt goes here, if any)
```

#### Follow-up — the Reflection written out in full

Across several messages the operator supplied their own text for every section and asked for light edits only, then reshaped the tab: sections 1 and 2 merged, the blank comparison tables dropped from section 1, and the "Main lesson from the experiment" box deleted. Sections 3 and 4 were retitled in the operator's own words ("What other problems could this agent team solve?").

Total edits made to the operator's writing: **three** — one missing article and one comma in the ticket-101 evaluation, and one word-order change ("also could" → "could also") in section 2. Arguments, ratings, structure and voice left as written.

Two accuracy checks were run rather than assumed. Every MCP tool named in section 3 was confirmed to exist in `mcp_server/server.py`. All three capability gaps claimed in section 4 were confirmed against the schema: `vendors` genuinely has no SKU column (and the server's own `notes_on_data` says `no_sku_vendor_link`), there is no shipment or purchase-order table, and there is no payroll, scheduled-payment or forecast table. The final tab contains 10 prose boxes and no blanks.

#### Follow-up — Section 1 filled in, and merged with Section 2

```text
For Section 1 — Evaluation of Performance, replace the blank template with the following reflections. Keep my ideas, ratings, and overall voice. You may make only light edits for clarity, grammar, and natural English. Do not substantially rewrite the argument or make it sound overly polished.

[Operator's own evaluations supplied in full: Ticket 101 at 4/5 stars, Ticket 102 at 4.5/5, Ticket 103 at 3.5/5.]
```

```text
Ohh also i think we should merge section 1 and 2 of the reflection.
```

The three evaluations were inserted verbatim apart from two touches — one missing article and one comma — leaving the argument, ratings and voice as written. Sections 1 and 2 were then merged into a single per-ticket section ("Evaluation of performance & Actual vs Expected"), since both are organised by ticket; the remaining sections renumbered to 2-4. Star ratings render as chips beside each ticket heading. 58 boxes remain blank; only the three evaluation boxes carry content.

## Problem 11 — Submit to GitHub

### Prompt(s)

```text
Let's move forward with Problem 11 — Submit to GitHub.

This is the final packaging and submission step for HW5. The working application is already complete; do not redesign the architecture or change working business logic unless a genuine packaging issue requires it.

Verify the hw5/ file structure against the attached reference tree. Do not delete implementation files genuinely required for the working agent system, backend or frontend merely to match the screenshot; remove only clearly unnecessary temporary/debug/cache files, and exclude Python caches, frontend build artifacts and machine-specific files.

Verify .gitignore protects .env, Python caches, .pyc, virtual environments, node_modules, Vite build output, OS temporary files and IDE files — without ignoring .env.example, .mcp.json, either database under data/, or the required output deliverables.

Secret audit (critical): confirm .env is ignored, not staged and not tracked; check the files that will be committed for API keys, tokens or passwords, paying special attention to PORTKEY_API_KEY, GitHub tokens, .mcp.json, logs, audit files and configuration. Keep .env.example with placeholder names only. If a real secret has already entered Git history, do NOT push publicly — stop and say what needs sanitizing.

Both data/campus_customs.db and data/campus_customs_new.db must be committed.

Finish README.md so a grader can clone and run the project: project overview, setup, clean database run, how to start the MCP server, the FastAPI backend and the React dashboard using the actual commands, how to do a full three-ticket run, and where the main deliverables live. Do not include the real key and do not invent commands.

Run a reproducibility check, inspect Git state before committing, create a clean final commit, and push to a PUBLIC repository under my authenticated GitHub account. Then verify the repository exists, is public, has the latest commit, can be cloned, does not contain .env, and does contain both database files. Write the final URL to output/github_url.txt and push it.
```

### What was lacking

Nothing blocking. Two things the brief could not have known: the real `.env` lives one directory above `hw5/`, so a repository rooted at `hw5/` cannot physically contain it; and `.mcp.json` carries absolute paths from the build machine, which is not a secret but is worth a caveat for anyone cloning — a note was added to the README rather than editing the file, since the brief asked to keep it.

### Additional prompt(s)

```text
(no follow-up prompt was needed)
```

#### Outcome

Public repository: **https://github.com/robmendozah/hw5** — 68 files, two commits, branch `main`, local and remote HEAD identical.

Created `.gitignore`, `.env.example` and `README.md`; removed `__pycache__`. Verified by cloning the public repository fresh and sweeping it: no `.env` in the working tree or anywhere in history, no live key and no key-shaped literal in any of the 68 files including both binary databases, and zero tracked files under `node_modules`, `__pycache__`, `.venv` or `dist`. Both databases are present at 53,248 bytes each.

The working database was committed in its post-Problem-9 state (two payments, three resolved tickets, $160.00) rather than reset, so the run evidence stays intact. `verify_problem5.py` passed 33/33 immediately before the commit; `test_api.py` was deliberately not run, because it mutates the database and would have destroyed that evidence.


### Prompt(s)

```text
(first prompt goes here)
```

### What was lacking

(one sentence on what the first prompt did not cover, or "No additional prompt was needed.")

### Additional prompt(s)

```text
(follow-up prompt goes here, if any)
```
