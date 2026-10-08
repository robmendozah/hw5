# Campus Customs — Multi-Agent Operations Desk (HW5)

A five-agent operations system for a small campus apparel shop. Agents read
shop facts through an MCP server, prepare consequential actions, and a human
approves them through a React dashboard. Nothing financial happens without a
signature.

## What it is

| Layer | Implementation |
|---|---|
| Agents | **PydanticAI** — Boss, Inventory, Accounting, Facilities, Customer Service, with full any-to-any delegation |
| Tools | **FastMCP** server exposing 14 named business tools (no arbitrary SQL) |
| Data | **SQLite** — `data/campus_customs_new.db` |
| API | **FastAPI** at `http://localhost:8000` |
| Dashboard | **React + Vite + TypeScript** at `http://localhost:5173` |
| Model | `gpt-6-luna` via Portkey (OpenAI-compatible) |

```
React dashboard → FastAPI → agent team / MCP server → campus_customs_new.db
```

**Human approval is structural, not advisory.** Agents can only *prepare* a
payment; the amount is read from the database and stored on the proposal, so no
caller can submit an arbitrary figure. Execution requires a one-time token that
the approval route mints only when a person clicks Approve, and the payment is
still refused if it would drive cash below zero. Closing a ticket works the same
way: agents may request it, only a human can grant it.

## Setup

```bash
git clone https://github.com/robmendozah/hw5.git
cd hw5
```

**1. Python environment** (3.12+; developed on 3.14)

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

**2. Frontend dependencies**

```bash
cd frontend
npm install
cd ..
```

**3. Credentials**

```bash
cp .env.example .env
```

Then open `.env` and set your own key:

```
PORTKEY_API_KEY=your_key_here
```

`.env` is git-ignored and is never committed. No real key is in this repository.

## Clean database run

Two database files ship with the repo:

| File | Role |
|---|---|
| `data/campus_customs.db` | **Pristine source.** Read-only. Never modified. |
| `data/campus_customs_new.db` | **Working copy.** The MCP server reads and writes this one. |

To restore the working copy to its original state:

```bash
python reset_db.py
```

`reset_db.py --check` reports drift without changing anything, and `--yes` skips
the confirmation prompt. The script refuses to run if the pristine original has
itself drifted from its recorded baseline, verifies the copy by hash afterwards,
and appends a `database_reset` record to the audit trail.

The dashboard's **Reset Workday** button and `POST /reset` do the same thing and
are fully working. Neither ever erases `output/audit_trail.json` — the trail is
append-only evidence across runs.

## Running it

Three things run. Start them in this order.

**1. MCP server — started automatically, no separate command**

The FastAPI backend launches the MCP server as a stdio subprocess on startup
(`backend/agents.py` → `build_mcp_toolset`), so there is nothing to start by
hand. `.mcp.json` is the same server configured for a desktop MCP client, and
`mcp_server/README.md` documents every tool.

One caveat for anyone cloning this: `.mcp.json` records absolute paths from the
machine it was built on. The backend does not read that file — it resolves paths
itself — so the app runs fine without touching it. Only adjust the two paths if
you want to attach the server to your own desktop MCP client.

To exercise the server on its own:

```bash
.venv/Scripts/python.exe mcp_server/server.py
```

It speaks MCP over stdio and will appear to hang — that is correct.

**2. FastAPI backend**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Runs at `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs`.

**3. React dashboard**

```bash
cd frontend
npm install     # first time only
npm run dev
```

Runs at `http://localhost:5173` and calls the backend at `http://localhost:8000`.
The API base URL lives in `frontend/.env.development` as `VITE_API_BASE_URL`.

## A full three-ticket run

1. **Reset the working database first** — `python reset_db.py`. Checking
   balance returns to **$3,400.00**, the payments table empties, and all three
   tickets return to `open`.
2. Start the backend, then the dashboard.
3. Open a case folder in the Inbox and press **Assign Team**.
4. Watch the Live Office Feed. Agents delegate and call MCP tools in real time.
5. **Financial actions stop and wait for you.** A prepared payment appears in
   the Approval Tray and on the case file as *Needs your signature*. Nothing
   moves until you click Approve. Insufficient cash is refused even after
   approval.
6. Close the case with **Mark case resolved**. Agents may request closure; only
   you can grant it.
7. Repeat for the remaining tickets. Run them in order — they share one evolving
   database.

For reference, the recorded run in `output/` went
**$3,400.00 → $2,560.00 → $160.00**: invoice 501 settled for $840.00 on ticket
101, rent of $2,400.00 paid on ticket 102, and no cash movement on ticket 103.

## Deliverables

| File | What it shows |
|---|---|
| `output/desk_tickets.html` | Expected plans vs. Actual results per ticket, the cash reconciliation, and the written reflection |
| `output/resolved_board.html` | Dashboard screenshots of each resolved case, captured as each one closed |
| `output/resolved_tickets.json` | Structured per-ticket evidence from the real run |
| `output/audit_trail.json` | Append-only log of every delegation, tool call, approval and execution |
| `output/harness.md` | Full system documentation — database, tools, agents, routes, shop rules, limits |
| `output/design.md` | Dashboard design rationale |
| `output/mcp_smoke.json` | Problem 4 MCP tool smoke tests |
| `AI_prompts.md` | Every prompt used to build the project |

## Verification

The system was checked by two scripts during development — 33 structural checks
on the agents, tools, limits and audit trail, and 28 end-to-end checks against a
running backend covering the approval controls. Both passed in full. The checks
and their results are documented in `output/harness.md`; the scripts themselves
are not part of the submission.

The controls they cover can be exercised directly through `/docs` or the
dashboard: an approval cannot carry an arbitrary amount, a payment is refused
when cash is short even after approval, the same proposal cannot execute twice,
and a reset never erases the audit trail.

## Repository layout

```
hw5/
├── backend/          FastAPI layer + the five agents and their prompts
├── mcp_server/       FastMCP server — the only path to shop data
├── frontend/         React + Vite + TypeScript dashboard
├── data/             pristine and working SQLite databases
├── output/           deliverables and evidence
├── proposal_store.py payment proposals awaiting human approval
├── resolution_store.py ticket-closure requests awaiting human confirmation
└── reset_db.py       restores the working database to baseline
```
