# Campus Customs — Regional Operations Desk

Design notes for the Problem 8 dashboard (`frontend/`, React + Vite +
TypeScript, talking to the FastAPI backend at `http://localhost:8000`).

## 1. The concept

The dashboard is a **physical operations desk viewed from above**. The browser
window is the desk surface — a brown wood wash under a faint fluorescent sheen
— and everything on it is an object you would actually find on one: an inbox
of folders, an open case file, a staff directory, a printout of the day's
activity, an out-tray of documents waiting to be signed, and a clipped memo.

Nothing is a "widget". A ticket is a folder. A payment request is a piece of
paper with a red border. An approval is a rubber stamp. The interface is a
desk, and the operator works it the way they would work a real one.

## 2. The mundane-office inspiration

The joke, such as it is, runs quietly underneath: five language-model agents
coordinate through an interface that looks like a regional branch office that
last updated its stationery in 2007. Beige partitions, manila card, a dot-matrix
activity sheet, laminated name badges, sticky notes curling at the corners.

The humour comes entirely from that contrast, and it is kept dry on purpose.
There are no cartoon avatars, no characters, no branded references, no gags in
the copy. Two sticky notes carry actual operating rules —
*"No payment without approval."* and *"Vendor won't ship with an unpaid
invoice."* — so even the decoration is load-bearing. The test applied
throughout was whether someone would be happy operating this every day, not
whether it would get a laugh once.

## 3. Why tickets are manila folders

Because a ticket **is** a case file, and a stack of folders communicates three
things at once that a table row does not:

- **There are exactly three of them.** The workload is graspable at a glance.
- **One is open and the others are not.** The selected folder slides out from
  the stack, exactly as if pulled.
- **Status is a coloured tab.** Muted blue for open, mustard for running,
  red-orange for needs-signature, green for resolved, stamp-red for attention.
  The operator reads the state of the whole desk peripherally, without reading
  a word.

Each folder carries only what identifies the case — number, type, counterparty,
one-line issue. Database detail belongs inside the file, not on its cover.

## 4. Why agents are coworkers on a staff roster

The five agents appear as office nameplates with initials, a job title, a
status light and a line describing what they are doing right now. This framing
does real work:

- **It makes delegation legible.** "Inventory is waiting on Accounting" is
  immediately meaningful in a way that "agent_2 → agent_3" is not.
- **It gives each agent a stable identity** through a restrained colour accent —
  burgundy for the Boss, warehouse blue for Inventory, accounting green,
  facilities ochre, faded teal for Customer Service.
- **It keeps them honest.** Status is derived from real audit events, and after
  a run only the agents the backend credits are marked Done. Everyone else
  stays Idle. The roster never implies participation that did not happen — in
  testing, a ticket-101 run correctly left Accounting and Facilities idle.

**Pixel staff.** Each nameplate carries a 16x16 pixel figure at a desk, drawn
as SVG rects with `shape-rendering: crispEdges`, in that agent's own colour
against a cubicle wall. Added at the operator's request, which relaxes the
original "no avatars" rule — they are kept small, muted and seated at work, so
the board still reads as an operations desk rather than a game.

The movement is a readout, not decoration. Each figure has two frames, and the
status the backend reported decides which plays:

| Status | What the figure does |
|---|---|
| Working | hands type at ~0.45s, figure bobs, desk lamp warms |
| Delegated | still, a coloured token drifts off to the right |
| Waiting | the same typing cycle at half speed, restless |
| Done | at rest, a small green tick, slow blink |
| Idle | still and slightly dimmed, occasional blink |

Under `prefers-reduced-motion` every figure drops to a single still frame with
the lamp and tick intact, so the state is still legible without any animation.

They read as colleagues at work, not characters. The status glyphs (○ ● → ✓ !)
remain alongside, typographic rather than illustrative.

## 5. How the Live Office Feed makes multi-agent work understandable

A five-agent system with nested delegation is genuinely hard to follow. The
feed renders it as an internal activity printout on tractor-feed paper: time,
who, what — one line each, newest first.

Four kinds of entry are visually distinct by left border colour, because
conflating them is what makes multi-agent logs unreadable:

| Entry | Colour | Example |
|---|---|---|
| Delegation | institutional blue | `INVENTORY → ACCOUNTING  Vendor invoice blocks shipment` |
| MCP tool call | desk brown, shown as a small stamped label | `MCP · get_vendor_shipping_status` |
| Outcome | office green | `Case closed out — completed.` |
| Approval / payment | accounting green | `Payment executed — amount: 840 · balance after: 2560` |
| Error / refusal | stamp red | `Payment refused — insufficient_cash.` |

Only the sanitized summaries the backend already returns are rendered. There is
no chain-of-thought here, and no path to it: the audit trail does not carry
reasoning, and the formatter reads nothing but named fields.

The feed polls **only while a run is active**, every 3 seconds, and stops when
the run ends. A still board is both calmer to watch and kinder to the backend.

## 6. Why proposals go in a "Needs Signature" tray

This is the most important piece of the interface, so it is the most physical.

A prepared payment appears as a red-bordered document in the out-tray, headed
**NEEDS SIGNATURE**, showing only backend-verified details: type, invoice or
lease number, account, amount, case, and the reason the agent gave.

The design makes the control structure visible rather than merely enforcing it
out of sight:

- The amount is displayed but **not editable**, and a line of fine print says
  so: *"Amount is read from the ledger by the backend. This desk cannot change
  it."* That is literally true — the approve call sends only `approved_by`.
- The stamp appears **only after the backend confirms execution**. In testing,
  an approval refused for insufficient cash produced no stamp at all — just the
  backend's own sentence: *"Insufficient cash: balance 160.0, payment 2400.0.
  Cash may never go negative, and human approval does not override this."*
- Approving feels consequential: a weighted green button with a physical press,
  then a rubber stamp that lands with a single quick animation.

A human signature is the one thing in this system that a model cannot supply,
so the interface gives it the weight of a physical act.

**Where the signature can be given.** Testing surfaced a real dead end: a run
can recommend a payment without any agent having prepared one, leaving the
operator with advice and nowhere to act. Approval now surfaces in three places,
and the gap itself is named rather than hidden:

- **On the case file**, inline under a *Your signature* divider — the same card
  component as the tray, so you sign where you are already reading. It renders
  from the proposal list, not from run state, so it survives a page reload.
- **In the out-tray**, as before, for everything awaiting a signature.
- **In the masthead**, as a red `N awaiting your signature` badge that scrolls
  to the request.

And when the team recommends a payment but prepared nothing, the case file says
so plainly and offers **Draw up the payment for signing** — a request the
operator initiates, which still sends only a ticket id, still reads the amount
from the ledger, and still requires the signature afterwards.

The approve button carries the figure (`Approve $2,400.00`), so the amount
being authorised is on the control itself rather than only above it.

## 7. How cash is presented

A small accounting slip in the masthead — faint green ruled lines, a dark green
left rule, the balance in monospace:

```
CHECKING ACCOUNT
Available balance
$3,400.00
```

Deliberately **not** a trading terminal: no tickers, no sparklines, no red/green
deltas. It is the shop's bank balance on a ledger card. Unpaid invoices appear
beneath it in small red type, because that is the number that constrains what
the desk can actually do.

The balance is never computed in the browser. When a backend-confirmed payment
lands, the card refetches `/cash` and the new figure arrives with a single
two-second green wash — enough to notice, not enough to distract.

## 8. Resolved tickets and agent contributions

Resolved folders **stay in the inbox** with a green rubber stamp on the cover.
They remain selectable, and opening one still shows the recommendation, the
limitations, any customer draft, and which agents participated. Work that is
finished is still evidence.

After a run, a **Case Notes** memo appears clipped to the board — a paperclip
drawn in CSS at the top edge — with one short line per agent describing what
that agent actually contributed, built from its own returned facts and
calculations. Below it, the MCP tools the run genuinely used appear as small
stamped labels, and a footer gives the mechanical truth: steps, handoffs,
delegation depth, stop reason.

Only agents the backend lists in `agents_involved` appear. An absent agent is
simply absent.

## 9. Why this makes the system easier and more enjoyable to operate

A multi-agent system fails a human operator in three specific ways: you cannot
tell what is happening, you cannot tell what is true, and you cannot tell what
it is about to do with your money. The desk metaphor answers each one with a
physical affordance rather than a label.

- **What is happening** — folder tabs and status lights give peripheral
  awareness; the feed gives the detail when you want it.
- **What is true** — every figure on the board is read from the backend, and
  the footer says so. The UI holds exactly one piece of state the backend
  cannot know (that a run request is in flight) and invents nothing else. A
  folder is never marked resolved because an animation finished.
- **What it will do with money** — nothing, until a human stamps it. And the
  stamp only lands after the backend says the money actually moved.

The office styling is not decoration on top of that; it is how the guarantees
are communicated. A red-bordered document in an out-tray says "this is waiting
on you" more immediately than any badge, and a stamp that refuses to appear
says "that did not happen" more honestly than a toast.

## Implementation notes

- **Architecture.** `React → FastAPI (:8000) → agent team / MCP → campus_customs_new.db`.
  The frontend opens no database, computes no balance, executes no payment and
  marks nothing resolved without backend confirmation.
- **API base URL.** A single `VITE_API_BASE_URL` in `.env.development`
  (`src/api.ts` is the only module that reads it). CORS on the backend allows
  `http://localhost:5173` and `http://127.0.0.1:5173` only — no wildcard.
- **Typography.** Three families: Roboto Slab for case-file headings, Inter for
  UI, JetBrains Mono for the activity log and ledger.
- **Motion.** Folders slide, cards lift, events fade in, working lights pulse,
  the stamp lands, the ledger washes green. All of it is suppressed under
  `prefers-reduced-motion`.
- **Responsive.** Three columns collapse to two at 1180px and one at 860px,
  where the approval tray is promoted above case notes so the thing needing a
  human stays prominent. Verified at 375px with no horizontal overflow.
- **Known limitation.** Run outcomes (the Case Notes memo and the in-file
  recommendation) live in browser state, because the backend exposes no route
  that returns a past run's resolution. Reloading the page clears the memo;
  folder status, cash, feed and **pending signatures** all survive, because
  those come from the backend. Persisting outcomes would need a backend change,
  which was out of scope for this problem.

## Running it

```
cd backend && uvicorn main:app --reload --port 8000
cd frontend && npm run dev
```

Then open `http://localhost:5173`.
