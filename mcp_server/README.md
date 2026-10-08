# Campus Customs MCP Server

Shared, database-grounded tools for the HW5 Campus Customs agents. Instead of
giving an agent raw database access, this server exposes a small number of
named business capabilities, each backed by fixed SQL.

## Database

Reads `data/campus_customs_new.db`, the working copy made in Problem 2. The
original `data/campus_customs.db` is never opened by this server.

## Read-only by default

Every tool except `execute_approved_payment` is read-only: the connection is opened in SQLite's
read-only mode and no tool writes, updates or closes anything. No tool accepts
arbitrary SQL — there is deliberately no `run_sql`-style escape hatch.

## Tools

Fourteen tools. Twelve are read-only: three ticket-scoped from Problem 3, five
from Problem 5 covering questions the ticket-scoped tools structurally cannot
answer, and one from Problem 6 that evaluates a shop rule deterministically.
Problem 7 adds two payment tools — one that only prepares, and one that writes
but is unreachable by any agent.

### Ticket-scoped (Problem 3)

- **`get_customer_order_fulfillment_context(ticket_id)`** — for a customer-order
  ticket, returns the requested SKU/size/quantity alongside the on-hand
  inventory, a deterministic `can_fulfill` / `shortfall_quantity`, and the
  linked invoice and vendor.
- **`get_rent_payment_context(ticket_id)`** — for a rent-notice ticket, returns
  the linked lease's rent and due date, the shop's operating date from `desk`,
  the cash balance, and the days-until-due and post-payment balance implied by
  those values.
- **`get_price_override_context(ticket_id)`** — for a price-override ticket,
  returns the requested quantity against stock on hand (all sizes of the SKU
  included) plus unit cost, list price and list-price margin figures.

### Added in Problem 5

- **`list_open_tickets()`** — every ticket on the desk as a summary row, plus
  the operating date. Lets an agent triage without already knowing a ticket id,
  which none of the ticket-scoped tools permit.
- **`get_product_availability(sku, size=None)`** — stock for one SKU across all
  its sizes, independent of any ticket. The route to verified in-stock
  alternatives when a requested size is short. Inventory rows only; no pricing.
- **`get_cash_position()`** — all cash accounts and all invoices with days
  overdue, independent of any ticket. `get_rent_payment_context` reports cash
  only inside a rent ticket, so this is the only way to see the full obligation
  picture or an invoice not linked to a ticket.
- **`get_vendor_directory()`** — every vendor with specialty and quoted lead
  time. The fulfillment tool returns only the one vendor on a ticket's invoice;
  this lists all of them.
- **`get_payment_history()`** — payments actually recorded. The authoritative
  check on whether money moved. An empty list is positive evidence that nothing
  has been paid.

### Added in Problem 6

- **`get_vendor_shipping_status(vendor_id)`** — whether a vendor is currently
  blocked from shipping new product because it has an open unpaid invoice.
  Returns a decided `blocked` flag, the blocking invoices with days overdue, the
  amount that would unblock, and the vendor's quoted lead time. This encodes a
  shop rule in the tool rather than leaving an agent to cross-reference the
  invoice list and apply the rule itself. It reports a block and cannot clear
  one — no tool here can pay an invoice.

### Added in Problem 7 — the only write path

- **`prepare_payment_proposal(kind, reference_id, ticket_id)`** — records a
  proposed payment for a human to approve. `kind` is `invoice_payment`
  (reference_id = invoice id) or `rent_payment` (reference_id = lease id).
  **Moves no money.** The amount is read from the database here and stored on
  the proposal, so no later caller can substitute an arbitrary figure. This is
  the only payment-related tool an agent can use.
- **`execute_approved_payment(proposal_id, execution_token)`** — executes a
  human-approved payment. The only tool on this server that writes to the
  database. It requires a one-time 32-byte token minted by the backend's
  approval route when a human approves; the token is never returned by any
  tool, so **an agent cannot reach this path**. It re-reads the obligation from
  live data, refuses if the amount has drifted since approval, refuses if the
  payment would drive cash below zero — human approval does not override that —
  and writes the `payments` row, the `cash_accounts` balance and any invoice
  status change in a single transaction. On refusal it rolls back, leaving
  nothing partially written.

### Added after Problem 8 — shop rule 11

- **`prepare_stock_purchase(sku, size, quantity, ticket_id)`** — prepares a
  low-value restock for human approval. Moves no money and orders nothing. The
  amount is computed as `quantity × pricing.unit_cost`, so no caller names a
  figure. Refuses anything above the routine-restock cost cap
  (`STOCK_PURCHASE_CAP_USD`), and refuses when the inferred supplier has an
  open unpaid invoice, because a blocked vendor will not ship. On execution the
  inventory increment happens in the same transaction as the cash deduction.

### Added in Problem 9 — closing a case

- **`request_ticket_resolution(ticket_id, summary)`** — lets an agent *ask* a
  human to close a case, with a stated reason for why it can close. Writes
  nothing; the ticket stays open. This is the only resolution-related tool an
  agent can use.
- **`confirm_ticket_resolution(ticket_id, resolution_token, resolved_by)`** —
  writes `tickets.status = 'resolved'`. Requires a one-time token minted by the
  backend's resolve route when a human confirms, so **no agent can close its own
  case**. The second of only two write tools on this server.

Every other tool uses a read-only SQLite connection. `execute_approved_payment`
and `confirm_ticket_resolution` are the only exceptions and open a separate
read-write connection.

Each ticket-scoped tool reports `found: false` for an unknown ticket id and
refuses tickets whose `type` does not match, rather than guessing. Missing
linked rows come back as `null` with a `*_found` flag instead of invented
values. Every tool carries a `notes_on_data` block distinguishing declared
foreign keys from value-based joins, and flagging what the database does not
contain — notably that there is no approved override price, discount cap or
margin threshold anywhere in the schema.

Twelve of the fourteen tools are read-only. Nothing an agent can call creates a payment,
purchase order, price change, inventory movement or ticket closure, so an
agent claiming such an action has occurred is necessarily wrong.

Later homework problems may add more MCP tools, including ones that write.
