# Campus Customs — Harness

## Problem 2 — Study the Campus Customs Database

Source inspected read-only: `data/campus_customs.db`
Working copy for later problems: `data/campus_customs_new.db` (exact byte copy, verified openable)

Everything below is taken from the actual schema (`sqlite_master`, `PRAGMA table_info`, `PRAGMA foreign_key_list`) and the actual rows. The database has 9 tables.

### Tables

#### 1. `tickets` (3 rows)

Fields: `id` (INTEGER, PK), `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`

Declared foreign keys: `lease_id → leases.id`, `invoice_id → invoices.id`.

Why it matters: this is the agents' inbox — every unit of work arrives here, and the `type` field is what tells an agent which workflow (order, rent, pricing) applies.

#### 2. `inventory` (10 rows)

Fields: `sku`, `name`, `size`, `qty`, `location` — composite primary key `(sku, size)`.

Why it matters: an agent must check stock at the `(sku, size)` level before promising a customer order, since the same SKU can be in stock in one size and out in another.

#### 3. `pricing` (4 rows)

Fields: `sku` (TEXT, PK), `unit_cost`, `list_price`.

Why it matters: it gives the cost floor and list price an agent needs to decide whether a requested discount still leaves a margin.

#### 4. `vendors` (3 rows)

Fields: `id` (INTEGER, PK), `name`, `specialty`, `lead_days`.

Why it matters: when stock is missing, `specialty` and `lead_days` are what an agent uses to pick a supplier and state a realistic turnaround.

#### 5. `invoices` (1 row)

Fields: `id` (INTEGER, PK), `vendor_id`, `amount`, `due_date`, `status`, `description`.

Declared foreign key: `vendor_id → vendors.id`.

Why it matters: it holds the money owed to vendors, so an agent handling a bill knows the amount, the due date and whether it is still open.

#### 6. `leases` (1 row)

Fields: `id` (INTEGER, PK), `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`.

Why it matters: it is the authoritative rent amount and due date, so an agent can verify a rent demand against the lease instead of trusting the message.

#### 7. `cash_accounts` (1 row)

Fields: `name` (TEXT, PK), `balance`, `date`.

Why it matters: it is the spending limit — an agent should confirm the balance covers an obligation before committing to pay it.

#### 8. `payments` (0 rows)

Fields: `id` (INTEGER, PK), `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`.

No declared foreign keys; `kind` plus `ref_id` is a generic pointer back to whatever was paid (e.g. an invoice or lease row).

Why it matters: it is the empty audit log where an agent records what it paid, from which account, and on whose approval.

#### 9. `desk` (1 row)

Fields: `date_today`, `notes`. No primary key.

Why it matters: it supplies the shop's "today" (`2026-08-31`), which is what makes a due date count as upcoming or overdue.

### Relationships

Declared in the schema:

- `tickets.lease_id → leases.id`
- `tickets.invoice_id → invoices.id`
- `invoices.vendor_id → vendors.id`

Not declared as foreign keys, but joinable by matching values:

- `tickets.sku` / `tickets.size` line up with `inventory.sku` / `inventory.size`
- `tickets.sku` and `inventory.sku` line up with `pricing.sku`
- `payments.ref_id` points at a row in another table, with `payments.kind` indicating which one

### The three open tickets

All three rows in `tickets` have `status = 'open'`. None were modified.

**Ticket 101 — `customer_order`, requester Tauhid Zaman, "Bulldog tee"**
Carries `sku = 'CC-TEE-WHITE'`, `size = 'S'`, `qty = 1`, and `invoice_id = 501`.
Links: `invoice_id` → `invoices.id = 501` (840.00, due 2026-08-28, status open, "Rush reprint CC-TEE-WHITE S"), which in turn links via `vendor_id = 1` → `vendors.id = 1` (Bulldog Print Co, apparel reprint, 5 lead days). By value, `(CC-TEE-WHITE, S)` matches `inventory` with `qty = 0`, and `CC-TEE-WHITE` matches `pricing` (unit_cost 8.00, list_price 28.00).

**Ticket 102 — `rent_notice`, requester Elm City Properties, "Rent due"**
Carries `lease_id = 1` and no SKU, invoice or quantity.
Links: `lease_id` → `leases.id = 1` (Chapel Street shop, landlord Elm City Properties, monthly_rent 2400.00, next_due 2026-09-02). Relevant context sits in `cash_accounts` (checking, 3400.00) and `desk.date_today` (2026-08-31).

**Ticket 103 — `price_override`, requester Yale AI Club, "Bulk hoodie discount"**
Carries `sku = 'CC-HOOD-NAVY'`, `size = 'M'`, `qty = 20`, and no `lease_id` or `invoice_id`.
Links: by value only — `(CC-HOOD-NAVY, M)` matches `inventory` with `qty = 8`, and `CC-HOOD-NAVY` matches `pricing` (unit_cost 22.00, list_price 58.00). It has no foreign-key link to any other table.

## Problem 3 — MCP Server (FastMCP)

Server: `mcp_server/server.py`. It opens `data/campus_customs_new.db` in SQLite read-only mode; the original `data/campus_customs.db` is not referenced anywhere in the code. All SQL is fixed inside the tool bodies and parameterised by ticket id — no tool accepts SQL from the caller, and there is no generic query tool.

### `get_customer_order_fulfillment_context(ticket_id)`

- **Reads:** `tickets`, `inventory`, `invoices`, `vendors`
- **Unlocks ticket:** 101
- **Why:** Ticket 101 asks for one `CC-TEE-WHITE` in size S, and the only way to answer "can we hand this customer a shirt today?" is to compare the ticket's `qty` against the `inventory` row for that exact `(sku, size)` — which is 0 — and then follow the ticket's `invoice_id` to invoice 501 and on to vendor Bulldog Print Co to see what reprint is already in motion.
- **Relationship note:** `tickets.invoice_id → invoices.id` and `invoices.vendor_id → vendors.id` are declared foreign keys; the `(sku, size)` match into `inventory` is a value-based join, so the tool reports `inventory_row_found` instead of assuming a row exists.

### `get_rent_payment_context(ticket_id)`

- **Reads:** `tickets`, `leases`, `cash_accounts`, `desk`
- **Unlocks ticket:** 102
- **Why:** Ticket 102 is an email claiming rent is due in two days, and the tool is what lets that claim be checked against the shop's own records — lease 1's `monthly_rent` of 2400.00 and `next_due` of 2026-09-02, measured against `desk.date_today` (2026-08-31) and the 3400.00 checking balance — rather than taken on the sender's word.
- **Relationship note:** `tickets.lease_id → leases.id` is a declared foreign key. `tickets.requester` and `leases.landlord` are independent text fields, so the tool returns both for comparison rather than treating the sender as verified.

### `get_price_override_context(ticket_id)`

- **Reads:** `tickets`, `inventory`, `pricing`
- **Unlocks ticket:** 103
- **Why:** Ticket 103 requests 20 hoodies in size M at a discount, so the two facts that decide it are whether 20 units exist in that size (only 8 do, a shortfall of 12) and how much room sits between the 22.00 unit cost and the 58.00 list price — both of which this tool returns, along with the other sizes of the SKU.
- **Relationship note:** both the `(sku, size)` match into `inventory` and the `sku` match into `pricing` are value-based joins, not declared foreign keys. The database holds no discount cap, approved override price or margin threshold, so the tool returns cost and price figures and explicitly says no pricing policy exists in the data.

### Shared behaviour

An unknown ticket id returns `found: false` with an explanatory error; a ticket whose `type` does not match the tool returns the actual type and declines. Linked rows that are absent come back as `null` next to a `*_found` flag, so a later agent can tell "no data" apart from "zero".

## Problem 5 — Agent Team and Expanded MCP Tools

Five PydanticAI agents with full any-to-any delegation, all reaching shop data
only through the `campus-customs` MCP server.

### Architecture

```
backend/
├── prompts/           one system-prompt file per agent
│   ├── boss.md
│   ├── inventory.md
│   ├── accounting.md
│   ├── facilities.md
│   └── customer_service.md
├── models.py          shared Pydantic contracts between agents
├── config.py          model name, Portkey settings, every hard limit
├── audit.py           append-only audit trail (harness behaviour)
├── agents.py          the five agents + the delegate tool + limit enforcement
└── runner.py          entry point: python -m backend.runner 101
```

The data path is `Agent → MCP tool → campus_customs_new.db → structured result
→ agent reasoning`. No module under `backend/` imports `sqlite3` or names a
database file; `verify_problem5.py` enforces this by walking the AST.

### Agents

Full connectivity: all five agents hold the same `delegate` tool, and its
`target_agent` parameter accepts any of the five roles. Every agent can
therefore delegate to every other agent — 20 ordered pairs, all live in code.
Self-delegation is refused, as is re-entering an agent already active in the
current chain.

| Agent | Role | Primary responsibilities | Tasks it should receive | Can delegate to |
|---|---|---|---|---|
| **Boss** | Orchestrator and final judgement | Read the ticket, choose specialists, coordinate, resolve conflicts, issue the final recommendation | Every ticket enters here; cross-functional decisions; escalations | All four others |
| **Inventory** | Stock and supply | Availability by SKU/size, shortfalls, fulfilment feasibility, vendor lead-time context | "Can we fill this order?", "What else is in stock?", "Who supplies this?" | All four others |
| **Accounting** | Financial analysis and control | Balances, invoices, unit cost, list price, margins, affordability, payment-status verification | "Can we afford this?", "What is the margin?", "Has this been paid?" | All four others |
| **Facilities** | Premises and occupancy | Leases, rent amounts, due dates, date comparisons against the shop's operating date | "When is rent due?", "What does this lease say?" | All four others |
| **Customer Service** | Customer-facing communication | Drafting replies, explaining stockouts, presenting verified alternatives | "Draft a reply to this customer" | All four others |

A specialist returns an `AgentResult`, which keeps four categories apart so the
next agent cannot confuse them: `verified_facts` (each naming the MCP tool that
produced it), `calculations` (with inputs and formula), `recommendation`
(explicitly judgement, with an approval flag), and `limitations`. The Boss
returns a `TicketResolution` in the same shape plus `agents_involved` and an
`actions_taken` list that stays empty because every tool is read-only.

### MCP tools

| Tool | Tables used | Business capability | Likely callers |
|---|---|---|---|
| `get_customer_order_fulfillment_context` | tickets, inventory, invoices, vendors | Can a customer-order ticket be filled, and what invoice/vendor sits behind it | Inventory, Boss |
| `get_rent_payment_context` | tickets, leases, desk, cash_accounts | Rent amount, due date, days remaining, whether cash covers it | Facilities, Accounting |
| `get_price_override_context` | tickets, inventory, pricing | Stock shortfall plus unit cost, list price and margin for a discount request | Accounting, Inventory |
| `list_open_tickets` | tickets, desk | Triage: what is on the desk, without knowing ids | Boss |
| `get_product_availability` | inventory | Stock for any SKU across sizes; verified alternatives | Inventory, Customer Service |
| `get_cash_position` | cash_accounts, invoices, vendors, desk | Full cash and obligation picture independent of a ticket | Accounting, Boss |
| `get_vendor_directory` | vendors | All vendors and quoted lead times for replenishment questions | Inventory |
| `get_payment_history` | payments | Whether money actually moved; empty means unpaid | Accounting, Boss |
| `get_vendor_shipping_status` | vendors, invoices, desk | Decides shop rule 3: is this vendor blocked from shipping by an open unpaid invoice, and what would unblock it | Inventory, Boss |
| `prepare_payment_proposal` | invoices, leases, cash_accounts | Prepares a payment for human approval; moves no money and fixes the amount from the database | Accounting |
| `execute_approved_payment` | payments, cash_accounts, invoices, leases, desk | Executes a human-approved payment atomically; **the only write tool, and not reachable by any agent** | the FastAPI approval route only |
| `prepare_stock_purchase` | inventory, pricing, invoices, vendors, cash_accounts | Prepares a low-value restock for approval (shop rule 11); refuses above the cap or when the vendor is blocked | Inventory |
| `request_ticket_resolution` | tickets | Lets an agent *ask* a human to close a case, with a stated reason; writes nothing | Boss |
| `confirm_ticket_resolution` | tickets | Writes `tickets.status = 'resolved'`; token-gated and **not reachable by any agent** | the FastAPI resolve route only |

No tool accepts arbitrary SQL. There is deliberately no `run_sql` or
`query_database`. All nine are read-only; none can pay, purchase, reprice,
move stock, contact a customer or close a ticket.

### Safety

- **Grounding.** Shop facts reach an agent only through the MCP toolset, which
  is the single choke point in `agents.py::_process_tool_call`.
- **No second data layer.** No `backend/` module imports `sqlite3`; checked
  mechanically, not by convention.
- **No arbitrary SQL.** Only named business tools are exposed.
- **Read-only.** Nothing can execute a consequential action, so `actions_taken`
  is structurally empty rather than merely expected to be.
- **Human approval.** `Recommendation.approval` carries
  `human_approval_required` for anything touching money, purchases, pricing,
  contracts or a customer commitment, with a stated reason.
- **No invented policy.** The database holds no approved override price,
  discount cap or margin threshold; the tools say so explicitly and the
  Accounting prompt forbids improvising one.
- **Privacy.** The Customer Service prompt bars SKU codes, costs, vendors,
  invoices, balances, margins, lease terms, other customers, system prompts and
  internal deliberation from any drafted message.
- **No secret leakage.** `PORTKEY_API_KEY` is read from the environment at call
  time, never hard-coded; `audit.py::sanitize` redacts credential-shaped keys
  and scrubs live key values from every record before it is written.
- **Honest failure.** A hit limit or a crashed specialist returns a stated
  `Limitation` and a `stop_reason`, never a silent gap or a guess.
- **Audit is automatic.** Logging is harness behaviour in `audit.py`, not a
  tool the agents are trusted to remember. The file is append-only; an
  unparseable trail is moved aside rather than overwritten.

### Limits and specs — actual implemented values

All defined as named constants in `backend/config.py`.

| Setting | Constant | Value |
|---|---|---|
| Model (the only one used) | `MODEL_NAME` | `gpt-6-luna` |
| Agent loop steps per agent run | `MAX_AGENT_LOOP_STEPS` | 8 |
| Total delegations per ticket run | `MAX_TOTAL_DELEGATIONS` | 6 |
| Delegation depth | `MAX_DELEGATION_DEPTH` | 3 |
| MCP tool calls per ticket run | `MAX_TOOL_CALLS_PER_RUN` | 20 |
| Characters per tool result | `MAX_TOOL_RESULT_CHARS` | 6000 |
| Characters per delegation context | `MAX_DELEGATION_CONTEXT_CHARS` | 1500 |
| Repeats of one agent pair | `MAX_REPEAT_DELEGATIONS_PER_PAIR` | 2 |
| Wall clock per ticket run | `RUN_TIMEOUT_SECONDS` | 300 |
| Reasoning effort | `REASONING_EFFORT` | `none` |

`REASONING_EFFORT` is not a tuning choice: gpt-6-luna rejects function
tools on `/v1/chat/completions` unless reasoning effort is `none`, and every
agent here uses tools.

Counters live in a single `RunState` shared by every agent in a run, so the
delegation and tool-call caps are global to the ticket rather than per agent.
Beyond the numeric caps, two structural guards prevent loops regardless of
count: self-delegation is refused, and delegating to an agent already active in
the current chain is refused as circular.

Reaching any limit does not raise. The delegation or tool call is refused with
an explanation the agent can act on, the refusal is written to the audit trail
with `stop_reason: limit_reached:<which>`, and the run finishes with
`completed_with_limits:<which>` in its `RunOutcome`.

### Audit trail

`output/audit_trail.json`, append-only, one JSON array. Each record carries
timestamp, run id, ticket id, step number, active agent, event type, and where
applicable the delegation source/target, depth, MCP tool name, and sanitized
argument and result summaries. Event types are `run_started`,
`mcp_tool_call`, `mcp_tool_result`, `tool_call_refused`, `delegation_sent`,
`delegation_result`, `delegation_refused`, `delegation_failed` and
`run_finished`. Never logged: the API key or any credential-shaped value,
full system prompts, or chain-of-thought.

## Problem 6 — Planning the Three Tickets

Planning only. No ticket was resolved and the working database was not modified
while producing this plan.

Deliverable: `output/desk_tickets.html`, a standalone page with one tab per open
ticket plus Cash and Reflection placeholders. Each ticket tab carries a filled
**Expected** section and an empty **Actual** section to be completed after the
agent run.

### Shop Rules / Operating Constraints

These ten rules are authoritative for both the expected plans and later agent
execution.

| # | Rule | Where it is enforced |
|---|---|---|
| 1 | `desk.date_today` is "today" for the shop. Use it to decide what is due or overdue; never the computer's clock. | Code: every date comparison in the MCP server reads `desk.date_today` (`get_rent_payment_context`, `get_cash_position`, `get_vendor_shipping_status`). Prompts: Boss, Accounting, Facilities, Inventory. |
| 2 | Vendor lead times come from the `vendors` table. Do not invent delivery timing. | Code: `get_vendor_directory` and `get_vendor_shipping_status` return `lead_days` with a `notes_on_data` caveat that it is a quote, not a confirmed date. Prompts: Inventory, Customer Service. |
| 3 | A vendor will NOT ship new product while that vendor has an open unpaid invoice. | **Code:** `get_vendor_shipping_status(vendor_id)` returns a decided `blocked` flag computed from `invoices.status`, so the rule is evaluated by the tool rather than reconstructed by an agent. Prompts: Inventory, Accounting, Boss. |
| 4 | Human approval is required before ANY payment. | Models: `Recommendation.approval` carries `human_approval_required` with a reason. Prompts: all five. **Not yet enforceable in code — see the gap note below.** |
| 5 | Points are deducted if payment approval is not obtained before payment. | Same as rule 4: approval must precede execution, never be reconstructed after. |
| 6 | If a payment is made, the relevant database table(s) must be updated. | Code: `get_payment_history` is the authoritative check — an empty `payments` table is positive evidence that nothing was paid. **No write path exists yet.** |
| 7 | If there is not enough cash, the payment tool must refuse. Balances may never go negative. | Code: `get_cash_position` supplies the balances for the pre-check. **The refusal itself requires the payment tool that does not yet exist.** |
| 8 | Cash only goes OUT. Revenue and customer inflows are not modelled; never add sale proceeds after fulfilling an order. | Code: no tool returns or writes revenue; the schema has no revenue table. Prompts: Boss, Accounting, Customer Service. |
| 9 | Before the later full run that resolves the tickets, reset the working database to the original values. | Workflow, not agent reasoning: `reset_db.py` (see *Resetting the database between runs*). Deliberately outside anything the agents can reach. |
| 10 | Do NOT email customers or call real vendors. Customer communications stay as drafts on the board; vendor actions stay internal. | Code: the server exposes no send, email, contact or order tool, so the constraint holds structurally. Prompts: Customer Service, Boss. |
| 11 | **Low-value auto-restock.** A small shortfall may be bought ahead without waiting for the customer to confirm, because being out of stock costs more than a few units do. Added at the operator's request after Problem 8. | **Code:** `prepare_stock_purchase` enforces all three bounds itself — a hard cost cap (`STOCK_PURCHASE_CAP_USD = 100.0`), a refusal when the supplier has an open unpaid invoice (rule 3), and an amount computed from `pricing.unit_cost` so no caller names a figure. Execution increments inventory in the same transaction as the cash deduction. Prompt: Inventory. |

#### Enforcement gap, stated honestly

Rules 4–7 describe the behaviour of a payment tool. **No payment tool exists in
this system as of Problem 6**, which is correct for a planning problem — the
brief asks only for narrowly necessary *read* capability. The consequence is
that these four rules are currently carried by prompt text and the
`human_approval_required` flag, which is exactly the prompt-only enforcement the
brief warns against for hard financial controls.

They become enforceable in code only when the payment tool is built. When it is,
it must itself:

- refuse any payment that would drive a cash balance below zero (rule 7),
- require an explicit approval token as a parameter and refuse without one,
  rather than trusting that approval happened upstream (rules 4 and 5),
- write the `payments` row and the updated `cash_accounts` balance in one
  transaction, so `get_payment_history` cannot disagree with the balance
  (rule 6).

Until then, the Accounting prompt states plainly that any payment it identifies
is a recommendation awaiting human action, not something in train.

#### Reset reminder

**Before the later full agent run that resolves the three tickets, restore
`data/campus_customs_new.db` to the original values from
`data/campus_customs.db`** — run `python reset_db.py`. This was *not* done as
part of Problem 6; planning changed no data.

### New MCP capability added during planning

Planning ticket 101 exposed one real gap. Rule 3 blocks a vendor from shipping
while it has an open unpaid invoice, and that rule gates the entire ticket 101
fulfilment path — but no tool evaluated it. The raw rows were reachable
(`get_cash_position` lists invoices with `vendor_id` and `status`,
`get_vendor_directory` lists vendors), so an agent could in principle
cross-reference two tool outputs and apply the rule itself. That is precisely
the prompt-only enforcement of a hard constraint that this problem rules out.

`get_vendor_shipping_status(vendor_id)` closes it: one narrow, read-only tool
that returns a decided `blocked` flag, the blocking invoices, the amount that
would unblock, and the vendor's quoted lead time. It is rule evaluation, not a
duplicate data view, and it adds no capability to act — it reports the block and
explicitly cannot clear one.

No other tool was added. Every other capability the three plans need already
existed.

## Problem 7 — Backend Routes (FastAPI)

`backend/main.py` is the HTTP surface and nothing more: no SQL, no business
rules, no ticket-solving logic. Shop facts are read through MCP tools, and the
single permitted mutation is also an MCP tool.

```
React dashboard -> FastAPI routes -> agent team (backend.runner) / MCP server
                -> data/campus_customs_new.db
```

### Routes

| Method | URL | What it does |
|---|---|---|
| `GET` | `/` | Service banner, model in use, and the route list. |
| `GET` | `/tickets` | Returns tickets 101–103 with their live status from the database, plus `is_open` / `is_resolved` and the shop's operating date. Nothing is hard-coded. |
| `POST` | `/tickets/{ticket_id}/run` | Validates the ticket exists, then calls `backend.runner.run_ticket` — the existing agent team. Returns the structured `RunOutcome`. Unknown ids get a 404. |
| `POST` | `/tickets/{ticket_id}/prepare-payment` | Prepares the payment that ticket implies, for a human to approve. Takes **only a ticket id** — the obligation is resolved from the ticket (lease or invoice) and the amount read from the database. Refuses a ticket with no payable obligation (400) and a duplicate pending request (409). |
| `GET` | `/events` | Recent agent activity from the append-only audit trail, newest first. Supports `?limit=` and `?ticket_id=`. |
| `GET` | `/approvals` | Prepared actions and their state. Supports `?status=`. Execution tokens are never included. |
| `POST` | `/approvals/{proposal_id}/approve` | Human approval. Executes the stored proposal through `execute_approved_payment`. |
| `GET` | `/cash` | Live cash position from `cash_accounts` via `get_cash_position`, with the checking balance called out. |
| `POST` | `/reset` | Restores `campus_customs_new.db` from the pristine original. Does not touch the audit trail. |
| `GET` | `/docs` | FastAPI interactive documentation. |

Run it:

```
cd backend
uvicorn main:app --reload --port 8000
```

### Route-level limits

| Setting | Constant in `backend/main.py` | Value |
|---|---|---|
| Events returned when no limit is given | `DEFAULT_EVENT_LIMIT` | 50 |
| Hard ceiling on events per request | `MAX_EVENT_LIMIT` | 500 (above this the request is rejected with HTTP 422) |
| Allowed CORS origins | `ALLOWED_ORIGINS` | `http://localhost:5173`, `http://127.0.0.1:5173` — the Vite dev server only, methods limited to GET and POST. No wildcard. |

### How an arbitrary payment is made impossible

The dangerous shape this design rules out is a frontend posting an amount and
the backend subtracting it. There is no route that accepts an amount at all.

```
agent calls prepare_payment_proposal
  -> amount is read FROM THE DATABASE and stored on the proposal
  -> frontend displays the proposal
  -> human clicks Approve
  -> POST /approvals/{id}/approve     (body carries only "approved_by")
  -> approval mints a one-time 32-byte execution token
  -> execute_approved_payment re-reads the obligation, re-checks cash
  -> payments row + balance + invoice status written in ONE transaction
```

Four independent things have to hold before any money moves, and each is
enforced in code rather than by prompt:

1. **The amount is never caller-supplied.** `ApprovalRequest` has exactly one
   field, `approved_by`. An amount sent in the body is ignored — verified by
   test, which posts `amount: 999999` against an $840 proposal and observes
   $840 execute.
2. **Human approval is structural.** `execute_approved_payment` refuses any
   proposal that is not `approved`, and approval only happens through the HTTP
   route. An agent has no file access and would have to guess 32 random bytes.
3. **Insufficient cash is refused regardless of approval.** The balance check
   runs inside the write transaction against live data. Human approval does not
   override it.
4. **Double execution is impossible.** Approving burns the token and moves the
   proposal out of `pending`; a second approval returns HTTP 409.

On any refusal the transaction is rolled back, so the database is never
partially modified.

### Reset behaviour

`POST /reset` restores the working database and **does not wipe
`output/audit_trail.json`** — the trail is append-only evidence across runs, and
the reset appends a `database_reset` record to it rather than removing history.
Proposals that the reset makes stale (`pending` or `approved`) are marked
`voided` rather than deleted; executed proposals are left untouched as evidence
of the previous run.

### Error handling

| Situation | Status |
|---|---|
| Ticket not found | 404 |
| Proposal not found | 404 |
| Proposal already executed, or not pending | 409 |
| Insufficient cash | 409 |
| Amount drifted since approval | 409 |
| Invoice already settled | 409 |
| Limit above the cap / malformed request | 422 |
| MCP tool failure | 502 |
| MCP not connected | 503 |
| Agent execution failure | 500, or a structured `RunOutcome` with an honest `stop_reason` |

Errors carry a short message only. No stack traces, secrets or internal paths
reach the frontend.

### Verification

`python test_api.py` with the backend running — **28/28 checks pass**, covering
all fourteen points from the assignment. It deliberately mutates the working
database (settling invoice 501, paying rent, then forcing an insufficient-cash
refusal) and restores it through `POST /reset` at the end.

## Problem 8 — Agent Dashboard (React + Vite + TypeScript)

`frontend/` is the human operations desk for the agent team. It consumes the
Problem 7 routes and duplicates none of their logic.

```
React dashboard (:5173) -> FastAPI (:8000) -> agent team / MCP -> campus_customs_new.db
```

### Files

```
frontend/
├── .env.development     VITE_API_BASE_URL=http://localhost:8000
├── src/
│   ├── api.ts           the only module that talks to the backend
│   ├── types.ts         mirrors backend/models.py
│   ├── useDesk.ts       desk state; the "never fake a transition" rules live here
│   ├── desk.ts          staff roster, event phrasing, formatting
│   ├── App.tsx          the desk layout
│   └── App.css          the office theme
```

### What the frontend is not allowed to do

Each of these is a structural property of the code, not a convention:

| Rule | How it holds |
|---|---|
| No direct database access | The frontend has no database client; `api.ts` is the only I/O. |
| No client-side cash arithmetic | The balance is whatever `GET /cash` returned. Nothing subtracts. |
| No client-side payment execution | Approving sends only `{approved_by}`; the amount lives on the stored proposal. |
| No resolving a ticket without the backend | Folder status derives from `ticket.is_resolved` and pending proposals. Local state tracks only "a run is in flight". |
| No invented events | The feed renders audit records returned by `GET /events`. |
| No simulated approvals | The stamp renders only after the approval route returns `executed: true`. |

### Polling

Events and proposals refresh every **1.2 seconds while a run is in flight**,
and not at all otherwise. Polling stops when the run returns.

Originally 3 seconds. Live runs turned out to finish in 2-5 seconds, so a 3s
poll frequently captured no activity at all and the Staff Room never showed
anyone working. Two fixes: the interval was shortened, and `staffStatuses` now
filters events to the **newest run for that ticket** — previously it mixed in
events from earlier runs of the same case and showed staff "working" who had
finished minutes before.

### Verification performed

Both servers running, exercised through the live dashboard:

| # | Check | Result |
|---|---|---|
| 3 | Three tickets display | 101, 102, 103 as manila folders |
| 4–5 | Select and run a ticket | Ticket 101 run live; folder went Open → Running → back with a recommendation |
| 6–7 | Real agent activity appears | Feed showed delegations, `get_product_availability`, `get_vendor_shipping_status`, `get_customer_order_fulfillment_context` |
| 8 | Correct participating agents | Roster showed Boss / Inventory / Customer Service as Done; Accounting and Facilities correctly stayed Idle |
| 9 | Completed ticket updates visually | Recommendation, limitations and Case Notes memo rendered |
| 10 | Financial action needs explicit approval | Prepared proposal appeared as NEEDS SIGNATURE; nothing moved until clicked |
| 11 | Approval goes through the backend | Approve sends only `approved_by`; cash is refetched, never computed |
| 12 | Cash refreshes after payment | $3,400.00 → $2,560.00 after a confirmed $840 payment, with the ledger wash |
| — | Refusals are honest | Second rent approval refused at $160; **no stamp**, balance unchanged, backend's own message shown |
| 13 | Errors do not break the UI | Backend stopped → "Office system temporarily unavailable" card, no stack trace; "Try the line again" recovered without a reload |
| 14 | Narrow viewport usable | 375px: columns stack, approval tray promoted, `scrollWidth === innerWidth` (no overflow) |
| 15 | `output/design.md` written | Covers all nine required points |

### Approval UX (revision)

A run can end recommending a payment without an agent having prepared one,
which left the operator holding advice and nothing to sign. Observed on a live
ticket-102 run: Accounting checked `get_rent_payment_context` and
`get_cash_position`, recommended approval, and never called
`prepare_payment_proposal`.

Four changes, in order of how much they are relied on:

1. **A deterministic fallback.** `POST /tickets/{id}/prepare-payment` lets the
   operator draw up the payment themselves. It takes only a ticket id; the
   obligation and amount still come from the database, and the result still
   requires a signature. The control model is unchanged — this adds a *prepare*
   path, not an execute path.
2. **Approval appears on the case file.** A pending request for the open case
   renders inline under a "Your signature" divider, using the same
   `ApprovalCard` component as the tray, so the two cannot disagree. It renders
   from the proposal list rather than from run state, so it survives a reload.
3. **A masthead badge.** `N awaiting your signature` in stamp red, which scrolls
   to the tray when clicked, and a one-time smooth scroll when a new request
   lands.
4. **The prompt was strengthened** — Accounting is now told that recommending a
   payment without preparing it is an incomplete answer. This is the weakest of
   the four and is treated as such: in the run tested after the change the
   agent still did not prepare, which is precisely why the deterministic path
   above exists rather than relying on prompt text.

The approve button now carries the amount (`Approve $2,400.00`) so the figure
being authorised is on the control itself.

### Shop rule 11 — low-value auto-restock (added after Problem 8)

Requested by the operator: a shirt that costs $8 at zero stock should not wait
on a customer confirmation.

`prepare_stock_purchase(sku, size, quantity, ticket_id)` prepares the restock.
It moves no money and orders nothing — it records a proposal that still needs a
human signature. The bounds are enforced in the tool, not in a prompt:

| Bound | Behaviour | Verified |
|---|---|---|
| Cost cap `STOCK_PURCHASE_CAP_USD = 100.0` | Above it, refused as a human decision rather than routine replenishment | 12 × CC-HOOD-NAVY = $264 → refused, `reason: above_cap` |
| Rule 3 still governs | A supplier with an open unpaid invoice will not ship, so the purchase is refused | 1 × CC-TEE-WHITE while invoice 501 open → refused, `reason: vendor_blocked` |
| Amount from the database | `quantity × pricing.unit_cost`; no caller names a figure | 5 × CC-MUG-CREST @ $3.50 → $17.50 |
| Cash and stock move together | The inventory increment is in the same transaction as the cash deduction | Approved: cash $3,400.00 → $3,382.50, mug stock 0 → 5, `payments` row `kind='stock_purchase'` |

Two honest limitations, both stated in the tool's own `notes_on_data`:

- **The schema has no vendor-to-SKU mapping.** A supplier can only be inferred
  from an invoice whose description names the SKU. For CC-TEE-WHITE that finds
  Bulldog Print Co; for CC-MUG-CREST it finds nothing, and the proposal says
  *"supplier not identifiable from the database"* rather than guessing.
- **The `payments` table has no item columns** — only kind, amount, account,
  date and approver. Which SKU a `stock_purchase` covers lives on the proposal
  and in the audit trail, not in `payments`.

Note what rule 11 does *not* do for ticket 101: vendor 1 is blocked by invoice
501, so buying the tee ahead is refused until the $840 is settled. The rule
changes nothing for that case, which is the correct outcome.

### Design documentation

See `output/design.md` for the concept, the reasoning behind folders, the staff
roster, the feed, the approval tray and the cash ledger, plus the one known
limitation (run outcomes live in browser state, so the Case Notes memo clears
on reload — the backend exposes no route returning a past run's resolution).

## Problem 9 — The Full Real Run

Tickets 101, 102 and 103 were run for real against one evolving working
database, with every financial action and every case closure performed by a
human through the dashboard. Nothing below is simulated or carried over from
the Problem 6 plan.

### Reset and starting position

`POST /reset` was called before any ticket ran. It reported `no_op` because the
working copy was already byte-identical to the pristine original, so equality
was **verified by hash rather than assumed**:

| | |
|---|---|
| `campus_customs_new.db` MD5 | `46effb90d8811f03e219ea9b5fbdfa5a` |
| Matches `campus_customs.db` | yes |
| **Starting checking balance** | **$3,400.00** (read from `cash_accounts`) |
| `payments` rows | 0 |
| Invoice 501 | open, $840 |
| Tickets | 101, 102, 103 all `open` |
| `desk.date_today` | 2026-08-31 |

The audit trail was **not** reset — it carried 562 prior records into this run
and a `problem9_run_started` event was appended to mark the baseline. The
database was not reset again between tickets.

### What actually happened

| Ticket | Run | First call | Agents | Approval | Cash |
|---|---|---|---|---|---|
| 101 | `run-76c939eaa6a4`, 41.3s, 25 steps, 3 delegations | Inventory | **$840.00** invoice 501 | Boss, Inventory, Accounting, Customer Service | $3,400 → **$2,560** |
| 102 | `run-51559a64167c`, 22.8s, 15 steps, 2 delegations | Facilities | **$2,400.00** rent | Boss, Facilities, Accounting | $2,560 → **$160** |
| 103 | `run-71b395c02671`, 19.1s, 19 steps, 3 delegations | Inventory | none required | Boss, Inventory, Accounting, Customer Service | unchanged **$160** |

Each ticket was paused after resolution so its screenshot records the balance as
it actually stood at that moment — $2,560.00, $160.00, $160.00 — rather than the
end state. An earlier pass captured all three images at the end, showing $160.00
on every one; that pass remains in the audit trail and was re-run rather than
re-captioned.

All three read `status = 'resolved'` in `tickets`. Full per-ticket evidence is
in `output/resolved_tickets.json`; the Expected-vs-Actual comparison is on each
ticket tab of `output/desk_tickets.html`.

### Cash reconciliation

| Line | Amount | Balance |
|---|---|---|
| Starting balance after verified reset | | **$3,400.00** |
| Ticket 101 — payment #1, invoice 501, Bulldog Print Co | − $840.00 | $2,560.00 |
| Ticket 102 — payment #2, rent, lease 1 | − $2,400.00 | $160.00 |
| Ticket 103 — no cash movement | − $0.00 | $160.00 |
| **Reconciled ending balance** | | **$160.00** |

This matches `cash_accounts.balance` for `checking` **exactly**. Both payments
carry `approved_by = "Front Desk"` in the `payments` table. Cash never went
negative, and no customer revenue was added — the $28 tee and the $1,160 of
hoodies at list are deliberately absent, because revenue is not modelled.

### Ticket resolution (added in Problem 9)

Problem 5 deliberately built no ticket-closing action, so `tickets.status`
could never change and no ticket could ever report `resolved`. Problem 9
requires that it can. Resolved at the operator's direction as
*agents request, humans confirm*:

- `request_ticket_resolution(ticket_id, summary)` — an agent asks, with a
  stated reason. Writes nothing.
- `confirm_ticket_resolution(ticket_id, resolution_token, resolved_by)` — the
  only write to `tickets.status`. Requires a one-time 32-byte token minted by
  `POST /tickets/{id}/resolve` when a human confirms, so no agent can close its
  own case.

The Boss requested closure on 102 and 103. It did not on 101 — that run
predates the capability. A human confirmed all three.

### Rule 3 outranks rule 11

Worth recording from ticket 101: Inventory tried to buy the single $8 shirt ahead
under shop rule 11, and `prepare_stock_purchase` **refused it** because Bulldog
Print Co was blocked by unpaid invoice 501. The cheap-restock rule does not
override the vendor-block rule, and that precedence is enforced in the tool
rather than left to the agent's judgement.

### Defect encountered and fixed

The first run of ticket 103 (`run-e714a91b3c6c`) aborted its Inventory
delegation:

```
[WinError 5] Access is denied: output\audit_trail.json.tmp -> output\audit_trail.json
```

OneDrive held the audit file open and the atomic replace lost the race. The
system degraded correctly — the delegation failed, was logged as
`delegation_failed`, and the Boss finished with an honest limitation rather
than crashing — but the Inventory review was lost. `audit.py`,
`proposal_store.py` and `resolution_store.py` now retry the replace with
backoff. Ticket 103 was re-run and went from 3 agents with an error to 4 agents
and 19 clean steps. **Both attempts remain in the audit trail**, marked with a
`rerun_after_defect` event.

### Where the plan and the run diverged

Kept visible rather than reconciled, because the differences are evidence:

- **101 — close to plan.** Boss → Inventory → **Accounting**, then Customer
  Service, exactly the chain Problem 6 predicted. Accounting prepared the
  payment itself rather than only recommending it. Unplanned: Inventory's
  attempt to buy the shirt ahead was refused by the vendor block.
- **102** — the plan had Facilities delegating onward to Accounting. The Boss
  delegated to both directly. Accounting stated plainly that no payment was
  prepared, so the operator route raised the proposal.
- **103** — the plan had the Boss open with Accounting as a pricing question.
  It opened with Inventory and fanned out to three specialists rather than
  running a chain. `get_vendor_shipping_status` and `get_cash_position` were
  planned but never needed. The Boss also did not request closure, so the
  operator closed the case directly.
- **Agents are inconsistent about preparing payments.** Accounting prepared on
  101 but not on 102, with no change in between. This is exactly why the
  deterministic `POST /tickets/{id}/prepare-payment` route exists — without it
  an operator can be left holding advice with nothing to sign.

### Deliverables

| File | Contents |
|---|---|
| `output/desk_tickets.html` | Problem 6 Expected preserved, Problem 9 Actual filled, Cash tab itemised |
| `output/resolved_tickets.json` | Per-ticket structured evidence from the real run |
| `output/resolved_board.html` | Three dashboard screenshots with captions, relative paths only |
| `output/resolved_board_images/` | `ticket_101.jpg`, `ticket_102.jpg`, `ticket_103.jpg` |
| `output/audit_trail.json` | 642 records, append-only, prior history intact |

---

# Final System Summary

The completed implementation, as it actually stands.

## Database

`data/campus_customs_new.db`, a working copy of the read-only original.

| Table | Rows | Role |
|---|---|---|
| `tickets` | 3 | The three cases. `sku`/`size` match inventory **by value**, not by foreign key. `lease_id` → `leases.id` and `invoice_id` → `invoices.id` are declared foreign keys. |
| `inventory` | 10 | Stock by (`sku`, `size`) composite key. |
| `pricing` | 4 | `unit_cost` and `list_price` per SKU; value-joined to inventory. |
| `vendors` | 3 | Specialty and quoted `lead_days`. **No vendor-to-SKU mapping exists.** |
| `invoices` | 1 | `vendor_id` → `vendors.id`. Status drives the vendor shipping block. |
| `leases` | 1 | Rent and `next_due`. Records no payment status. |
| `cash_accounts` | 1 | The checking balance. The only account. |
| `payments` | grows | Written only by `execute_approved_payment`. No item columns. |
| `desk` | 1 | `date_today` — the shop's today, governing every date comparison. |

## MCP tools

Thirteen tools. Eleven read-only; two write, both unreachable by any agent.

| Tool | Tables | Capability |
|---|---|---|
| `get_customer_order_fulfillment_context` | tickets, inventory, invoices, vendors | Can a customer order be filled, and what invoice/vendor sits behind it |
| `get_rent_payment_context` | tickets, leases, desk, cash_accounts | Rent, due date, days remaining, whether cash covers it |
| `get_price_override_context` | tickets, inventory, pricing | Shortfall plus unit cost, list price and margin |
| `list_open_tickets` | tickets, desk | Triage without knowing ids |
| `get_product_availability` | inventory | Stock for any SKU across sizes |
| `get_cash_position` | cash_accounts, invoices, vendors, desk | Full cash and obligation picture |
| `get_vendor_directory` | vendors | All vendors and quoted lead times |
| `get_payment_history` | payments | Whether money actually moved |
| `get_vendor_shipping_status` | vendors, invoices, desk | Decides shop rule 3 — is this vendor blocked |
| `prepare_payment_proposal` | invoices, leases, cash_accounts | Prepares a payment for approval; moves no money |
| `prepare_stock_purchase` | inventory, pricing, invoices, vendors, cash_accounts | Prepares a capped restock (rule 11) |
| `execute_approved_payment` | payments, cash_accounts, invoices, inventory, leases, desk | **Writes.** Executes an approved payment atomically |
| `confirm_ticket_resolution` | tickets | **Writes.** Closes a case after human confirmation |

Plus `request_ticket_resolution` (tickets, read-only — records a request). No
tool accepts arbitrary SQL; there is no `run_sql` or `query_database`, and no
tool takes a free-text `sql` or `query` parameter.

## Agent team

Five PydanticAI agents on `gpt-6-luna` through Portkey, with **full any-to-any
connectivity**: all five hold the same `delegate` tool and its `target_agent`
accepts any of the five roles — 20 ordered pairs, all live in code.

| Agent | Owns |
|---|---|
| **Boss** | Triage, delegation, conflict resolution, the final `TicketResolution` |
| **Inventory** | Stock, shortfalls, SKU/size matching, vendor supply context |
| **Accounting** | Balances, invoices, margins, affordability, payment preparation |
| **Facilities** | Leases, rent, due dates against the shop's calendar |
| **Customer Service** | Customer-facing drafts — never sent |

Specialists return an `AgentResult` keeping four things apart: `verified_facts`
(each naming its MCP tool), `calculations` (inputs and formula), a
`recommendation` labelled as judgement, and `limitations`.

## Backend API

`backend/main.py` — HTTP only, no SQL, no business rules, no ticket logic.

| Method | Route | Purpose |
|---|---|---|
| GET | `/tickets` | Tickets with live status |
| POST | `/tickets/{id}/run` | Runs the agent team |
| POST | `/tickets/{id}/prepare-payment` | Prepares the ticket's payment; takes only an id |
| POST | `/tickets/{id}/resolve` | Closes a case — the only write to `tickets.status` |
| GET | `/tickets/{id}/resolution-request` | Whether an agent asked for closure |
| GET | `/events` | Audit activity, newest first (default 50, max 500) |
| GET | `/approvals` | Prepared actions and their state |
| POST | `/approvals/{id}/approve` | Human approval; executes the stored proposal |
| GET | `/cash` | Live `cash_accounts` position |
| POST | `/reset` | Restores the working database |

## Dashboard

`frontend/` — React + Vite + TypeScript, styled as a regional operations desk.
`src/api.ts` is the only module that reaches the network; the UI opens no
database, computes no balance and executes nothing.

- Tickets are manila folders with status-coloured tabs.
- Agents are nameplates with animated pixel figures whose state is a readout of
  real audit events.
- The Live Office Feed renders sanitized audit records, distinguishing
  delegations, MCP tool calls, outcomes, approvals and errors.
- Approvals appear in the out-tray **and** inline on the case file; the stamp
  lands only after the backend confirms execution.
- Cash is an accounting ledger card, refetched after every confirmed payment.
- Events poll every 1.2s only while a run is in flight.

## Safety and business controls

| Control | How it holds |
|---|---|
| MCP is the only source of shop facts | No `backend/` module imports `sqlite3`; enforced by AST walk in `verify_problem5.py` |
| No fabricated data | Every fact carries its source tool; tools state what the database does not contain |
| Human approval before any payment | `execute_approved_payment` refuses anything not `approved`, and needs a one-time token only the approval route mints |
| No arbitrary amounts | `ApprovalRequest` has one field, `approved_by`. Amounts are database-derived and stored on the proposal |
| Cash never negative | Balance re-checked inside the write transaction; approval does not override it |
| Vendor unpaid-invoice constraint | `get_vendor_shipping_status` decides rule 3; `prepare_stock_purchase` refuses a blocked vendor |
| `desk.date_today` is the shop date | Every date comparison in the MCP server reads it; never the wall clock |
| Vendor lead times from the database | Returned with a caveat that a quote is not a confirmed delivery date |
| No customer emails or vendor calls | No send, email, contact or order tool exists |
| Revenue not modelled | No tool returns or writes revenue; the schema has no revenue table |
| Agents cannot close their own cases | `confirm_ticket_resolution` is token-gated behind the human resolve route |
| Loop/tool/delegation caps | See the limits table in the Problem 5 section; enforced in `agents.py`, not by prompt |
| Secrets and privacy | `PORTKEY_API_KEY` read from the environment at call time; `audit.sanitize` redacts credential-shaped keys and scrubs live key values before any record is written |

---

### Resetting the database between runs

`reset_db.py` restores `data/campus_customs_new.db` to the original baseline so
that a full ticket-resolution run always starts from the same world.

```
python reset_db.py --check     report drift, change nothing
python reset_db.py             reset after confirmation
python reset_db.py --yes       reset without prompting
```

**When it is required.** Every MCP tool is currently read-only, so the working
copy has never diverged and a reset is a no-op today. It becomes mandatory as
soon as a write tool exists: resolving ticket 102 records a payment, resolving
101 moves stock, and a second run would then start from a mutated world and be
neither reproducible nor comparable to the first. Run it before each full
resolution run once write tools are introduced.

**Why it is a harness script and not an MCP tool.** An agent able to reset the
database could erase the evidence of its own writes. The reset therefore sits
outside everything the agents can reach - the same reasoning that keeps audit
logging out of their hands.

**Guards.**

- The copy only ever goes original to working. `data/campus_customs.db` is
  opened read-only and is never a destination.
- The original is checked against a recorded baseline MD5
  (`46effb90d8811f03e219ea9b5fbdfa5a`) before anything is copied. If the
  read-only original has itself drifted, the script refuses with exit code 2
  rather than propagating the damage into the working copy.
- The copy is hash-verified after writing; a mismatch raises instead of
  reporting success.
- Overwriting prompts for confirmation unless `--yes` is passed.
- `--check` is side-effect free and exits non-zero on drift, so it can gate a
  run in a script.

**Audit.** A successful reset appends a `database_reset` record carrying the
working database name and the MD5 before and after, so a later reader can tell
exactly where one run's world ended and the next began. A no-op reset writes
nothing.

### Running it

```
python reset_db.py --check
python -m backend.runner 101
python -m backend.runner 101 102 103
python verify_problem5.py
```
