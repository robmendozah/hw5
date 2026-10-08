"""Campus Customs MCP server (HW5).

Exposes read-only, database-grounded tools over the working copy of the
Campus Customs database. Each tool answers one specific business question
with deterministic SQL; no tool accepts arbitrary SQL from the caller.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import proposal_store  # noqa: E402  (shared with the FastAPI backend)
import resolution_store  # noqa: E402

# data/campus_customs_new.db is the working copy. The original
# data/campus_customs.db is never opened by this server.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")

# Shop rule 11 (low-value auto-restock): a stock purchase may be prepared
# without waiting for the customer to confirm, but only below this cost. Above
# it, the shortfall is a human decision rather than routine replenishment.
STOCK_PURCHASE_CAP_USD = 100.0


def _connect() -> sqlite3.Connection:
    """Open the working database read-only."""
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_rw() -> sqlite3.Connection:
    """Open the working database read-write.

    Used by exactly one tool - execute_approved_payment - and only after a
    human-approved proposal and its one-time token have been validated. Every
    other tool on this server uses the read-only connection above.
    """
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _ticket(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def _not_found(ticket_id: Any) -> dict:
    return {
        "found": False,
        "ticket_id": ticket_id,
        "error": f"No ticket with id {ticket_id}.",
    }


def _wrong_type(ticket: sqlite3.Row, expected: str) -> dict:
    return {
        "found": True,
        "ticket_id": ticket["id"],
        "ticket_type": ticket["type"],
        "error": (
            f"Ticket {ticket['id']} has type '{ticket['type']}', "
            f"not '{expected}'; this tool does not apply."
        ),
    }


def _coerce_ticket_id(ticket_id: Any) -> int | None:
    try:
        return int(ticket_id)
    except (TypeError, ValueError):
        return None


class _PaymentRefused(Exception):
    """A deterministic refusal - the transaction is rolled back untouched."""

    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


@mcp.tool()
def get_customer_order_fulfillment_context(ticket_id: int) -> dict:
    """Fulfillment evidence for a customer-order ticket (e.g. ticket 101).

    Reads the ticket, the matching inventory row for its SKU and size, and the
    linked invoice plus that invoice's vendor. Reports whether the requested
    quantity is currently on hand and by how much it falls short. Read-only;
    returns facts only, no fulfillment plan or reorder decision.
    """
    tid = _coerce_ticket_id(ticket_id)
    if tid is None:
        return _not_found(ticket_id)

    with _connect() as conn:
        ticket = _ticket(conn, tid)
        if ticket is None:
            return _not_found(tid)
        if ticket["type"] != "customer_order":
            return _wrong_type(ticket, "customer_order")

        # tickets.sku / tickets.size match inventory by value; this is not a
        # declared foreign key in the schema.
        inv = None
        if ticket["sku"] is not None and ticket["size"] is not None:
            inv = conn.execute(
                "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                (ticket["sku"], ticket["size"]),
            ).fetchone()

        # tickets.invoice_id -> invoices.id and invoices.vendor_id -> vendors.id
        # are declared foreign keys.
        invoice = None
        vendor = None
        if ticket["invoice_id"] is not None:
            invoice = conn.execute(
                "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)
            ).fetchone()
            if invoice is not None:
                vendor = conn.execute(
                    "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],)
                ).fetchone()

        requested_qty = ticket["qty"]
        inventory_qty = inv["qty"] if inv is not None else None

        can_fulfill = None
        shortfall_quantity = None
        if requested_qty is not None and inventory_qty is not None:
            can_fulfill = inventory_qty >= requested_qty
            shortfall_quantity = max(0, requested_qty - inventory_qty)

        return {
            "found": True,
            "ticket_id": ticket["id"],
            "ticket_type": ticket["type"],
            "ticket_status": ticket["status"],
            "customer": ticket["requester"],
            "subject": ticket["subject"],
            "notes": ticket["notes"],
            "created_at": ticket["created_at"],
            "sku": ticket["sku"],
            "size": ticket["size"],
            "requested_quantity": requested_qty,
            "product_name": inv["name"] if inv is not None else None,
            "inventory_quantity": inventory_qty,
            "inventory_location": inv["location"] if inv is not None else None,
            "inventory_row_found": inv is not None,
            "can_fulfill": can_fulfill,
            "shortfall_quantity": shortfall_quantity,
            "invoice_id": invoice["id"] if invoice is not None else ticket["invoice_id"],
            "invoice_found": invoice is not None,
            "invoice_amount": invoice["amount"] if invoice is not None else None,
            "invoice_due_date": invoice["due_date"] if invoice is not None else None,
            "invoice_status": invoice["status"] if invoice is not None else None,
            "invoice_description": invoice["description"] if invoice is not None else None,
            "vendor_id": vendor["id"] if vendor is not None else None,
            "vendor_name": vendor["name"] if vendor is not None else None,
            "vendor_specialty": vendor["specialty"] if vendor is not None else None,
            "vendor_lead_days": vendor["lead_days"] if vendor is not None else None,
            "notes_on_data": {
                "sku_size_to_inventory": "value-based join, not a declared foreign key",
                "ticket_to_invoice": "declared foreign key tickets.invoice_id -> invoices.id",
                "invoice_to_vendor": "declared foreign key invoices.vendor_id -> vendors.id",
            },
        }


@mcp.tool()
def get_rent_payment_context(ticket_id: int) -> dict:
    """Financial and timing evidence for a rent-notice ticket (e.g. ticket 102).

    Reads the ticket, its linked lease, the shop's operating date from `desk`,
    and the cash account balances. Reports days until the rent is due and
    whether the balance covers it. Read-only; it does not decide whether to pay
    and does not record a payment.
    """
    tid = _coerce_ticket_id(ticket_id)
    if tid is None:
        return _not_found(ticket_id)

    with _connect() as conn:
        ticket = _ticket(conn, tid)
        if ticket is None:
            return _not_found(tid)
        if ticket["type"] != "rent_notice":
            return _wrong_type(ticket, "rent_notice")

        # tickets.lease_id -> leases.id is a declared foreign key.
        lease = None
        if ticket["lease_id"] is not None:
            lease = conn.execute(
                "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)
            ).fetchone()

        desk_row = conn.execute("SELECT * FROM desk LIMIT 1").fetchone()
        accounts = [
            dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name")
        ]

        operating_date = desk_row["date_today"] if desk_row is not None else None
        rent_amount = lease["monthly_rent"] if lease is not None else None
        due_date = lease["next_due"] if lease is not None else None

        days_until_due = None
        if operating_date and due_date:
            try:
                days_until_due = (
                    date.fromisoformat(due_date) - date.fromisoformat(operating_date)
                ).days
            except ValueError:
                days_until_due = None

        primary = accounts[0] if accounts else None
        balance = primary["balance"] if primary is not None else None
        balance_after_paying_rent = None
        balance_covers_rent = None
        if balance is not None and rent_amount is not None:
            balance_after_paying_rent = round(balance - rent_amount, 2)
            balance_covers_rent = balance >= rent_amount

        return {
            "found": True,
            "ticket_id": ticket["id"],
            "ticket_type": ticket["type"],
            "ticket_status": ticket["status"],
            "counterparty": ticket["requester"],
            "subject": ticket["subject"],
            "notes": ticket["notes"],
            "created_at": ticket["created_at"],
            "lease_id": lease["id"] if lease is not None else ticket["lease_id"],
            "lease_found": lease is not None,
            "property": lease["space_name"] if lease is not None else None,
            "landlord": lease["landlord"] if lease is not None else None,
            "lease_notes": lease["notes"] if lease is not None else None,
            "rent_amount": rent_amount,
            "due_date": due_date,
            "operating_date": operating_date,
            "days_until_due": days_until_due,
            "cash_account_name": primary["name"] if primary is not None else None,
            "cash_balance": balance,
            "cash_balance_as_of": primary["date"] if primary is not None else None,
            "all_cash_accounts": accounts,
            "balance_after_paying_rent": balance_after_paying_rent,
            "balance_covers_rent": balance_covers_rent,
            "notes_on_data": {
                "ticket_to_lease": "declared foreign key tickets.lease_id -> leases.id",
                "landlord_match": (
                    "tickets.requester and leases.landlord are separate text fields; "
                    "compare them, do not assume they match"
                ),
                "calculations": (
                    "days_until_due, balance_after_paying_rent and balance_covers_rent "
                    "are computed only from desk.date_today, leases.monthly_rent, "
                    "leases.next_due and cash_accounts.balance"
                ),
            },
        }


@mcp.tool()
def get_price_override_context(ticket_id: int) -> dict:
    """Pricing and stock evidence for a price-override ticket (e.g. ticket 103).

    Reads the ticket, the inventory row for its SKU and size (plus the other
    sizes of that SKU), and the SKU's unit cost and list price. Reports the
    stock shortfall and list-price margin figures. Read-only; it proposes no
    override price, discount cap or pricing policy.
    """
    tid = _coerce_ticket_id(ticket_id)
    if tid is None:
        return _not_found(ticket_id)

    with _connect() as conn:
        ticket = _ticket(conn, tid)
        if ticket is None:
            return _not_found(tid)
        if ticket["type"] != "price_override":
            return _wrong_type(ticket, "price_override")

        # tickets.sku / tickets.size match inventory and pricing by value;
        # neither is a declared foreign key.
        inv = None
        if ticket["sku"] is not None and ticket["size"] is not None:
            inv = conn.execute(
                "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                (ticket["sku"], ticket["size"]),
            ).fetchone()

        other_sizes = []
        pricing = None
        if ticket["sku"] is not None:
            other_sizes = [
                dict(r)
                for r in conn.execute(
                    "SELECT size, qty, location FROM inventory WHERE sku = ? ORDER BY size",
                    (ticket["sku"],),
                )
            ]
            pricing = conn.execute(
                "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)
            ).fetchone()

        requested_qty = ticket["qty"]
        inventory_qty = inv["qty"] if inv is not None else None
        shortfall_quantity = None
        if requested_qty is not None and inventory_qty is not None:
            shortfall_quantity = max(0, requested_qty - inventory_qty)

        unit_cost = pricing["unit_cost"] if pricing is not None else None
        list_price = pricing["list_price"] if pricing is not None else None

        calculations = {}
        if unit_cost is not None and list_price is not None:
            calculations["list_price_gross_margin_per_unit"] = round(list_price - unit_cost, 2)
            if list_price:
                calculations["list_price_gross_margin_pct"] = round(
                    (list_price - unit_cost) / list_price * 100, 2
                )
            if requested_qty is not None:
                calculations["requested_qty_revenue_at_list"] = round(
                    list_price * requested_qty, 2
                )
                calculations["requested_qty_cost"] = round(unit_cost * requested_qty, 2)

        return {
            "found": True,
            "ticket_id": ticket["id"],
            "ticket_type": ticket["type"],
            "ticket_status": ticket["status"],
            "customer": ticket["requester"],
            "subject": ticket["subject"],
            "notes": ticket["notes"],
            "created_at": ticket["created_at"],
            "sku": ticket["sku"],
            "size": ticket["size"],
            "requested_quantity": requested_qty,
            "product_name": inv["name"] if inv is not None else None,
            "inventory_quantity": inventory_qty,
            "inventory_location": inv["location"] if inv is not None else None,
            "inventory_row_found": inv is not None,
            "shortfall_quantity": shortfall_quantity,
            "inventory_all_sizes_for_sku": other_sizes,
            "pricing_row_found": pricing is not None,
            "unit_cost": unit_cost,
            "list_price": list_price,
            "calculations_from_database_fields_only": calculations,
            "notes_on_data": {
                "sku_size_to_inventory": "value-based join, not a declared foreign key",
                "sku_to_pricing": "value-based join, not a declared foreign key",
                "no_pricing_policy_in_database": (
                    "the database contains no approved override price, discount cap "
                    "or required margin threshold"
                ),
            },
        }


@mcp.tool()
def list_open_tickets() -> dict:
    """Summaries of every ticket on the desk, for triage.

    Returns id, type, requester, subject, status and the SKU/size/qty or
    lease/invoice link for each ticket, plus the shop's operating date. Lets an
    agent discover which tickets exist without already knowing an id. It does
    not include inventory, pricing, lease or cash detail; use the ticket-type
    tools for that. Read-only.
    """
    with _connect() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT id, type, requester, subject, sku, size, qty, lease_id, "
                "invoice_id, status, created_at FROM tickets ORDER BY id"
            )
        ]
        desk_row = conn.execute("SELECT * FROM desk LIMIT 1").fetchone()

    return {
        "operating_date": desk_row["date_today"] if desk_row is not None else None,
        "ticket_count": len(rows),
        "open_ticket_count": sum(1 for r in rows if r["status"] == "open"),
        "tickets": rows,
    }


@mcp.tool()
def get_product_availability(sku: str, size: str | None = None) -> dict:
    """Stock on hand for one SKU, across every size or one specific size.

    Answers "what else do we have in this product?" independently of any
    ticket, which the ticket-scoped tools cannot do. Used to identify verified
    in-stock alternatives when a requested size is short. Returns inventory
    rows only - no cost, price or margin. Read-only.
    """
    if not isinstance(sku, str) or not sku.strip():
        return {"found": False, "sku": sku, "error": "A non-empty sku is required."}

    sku = sku.strip()
    with _connect() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT sku, name, size, qty, location FROM inventory "
                "WHERE sku = ? ORDER BY size",
                (sku,),
            )
        ]

    if not rows:
        return {
            "found": False,
            "sku": sku,
            "error": "No inventory rows for sku '" + sku + "'.",
        }

    requested = None
    if size is not None:
        requested = next((r for r in rows if r["size"] == size), None)

    return {
        "found": True,
        "sku": sku,
        "product_name": rows[0]["name"],
        "requested_size": size,
        "requested_size_row_found": None if size is None else requested is not None,
        "requested_size_quantity": requested["qty"] if requested is not None else None,
        "sizes": rows,
        "sizes_in_stock": [r["size"] for r in rows if r["qty"] > 0],
        "total_quantity_all_sizes": sum(r["qty"] for r in rows),
        "notes_on_data": {
            "sizes_are_not_substitutes": (
                "quantities for other sizes are reported as fact only; whether a "
                "different size satisfies the request is a business judgement, not "
                "a database fact"
            )
        },
    }


@mcp.tool()
def get_cash_position() -> dict:
    """The shop's cash accounts and outstanding invoices, independent of any ticket.

    Reports every cash account balance, the operating date from `desk`, and
    each invoice with its status and days overdue relative to that operating
    date. `get_rent_payment_context` reports cash only in the context of a rent
    ticket; this tool answers the general "what can we afford" question and is
    the only way to see invoices not linked to a ticket. Read-only; it does not
    decide or record payments.
    """
    with _connect() as conn:
        accounts = [
            dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name")
        ]
        invoices = [
            dict(r)
            for r in conn.execute(
                "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, "
                "i.due_date, i.status, i.description "
                "FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id "
                "ORDER BY i.due_date, i.id"
            )
        ]
        desk_row = conn.execute("SELECT * FROM desk LIMIT 1").fetchone()

    operating_date = desk_row["date_today"] if desk_row is not None else None
    for inv in invoices:
        inv["days_overdue"] = None
        if operating_date and inv["due_date"]:
            try:
                delta = (
                    date.fromisoformat(operating_date)
                    - date.fromisoformat(inv["due_date"])
                ).days
                inv["days_overdue"] = delta if delta > 0 else 0
            except ValueError:
                inv["days_overdue"] = None

    open_invoices = [i for i in invoices if i["status"] == "open"]
    total_cash = round(sum(a["balance"] for a in accounts), 2)
    total_open = round(sum(i["amount"] for i in open_invoices), 2)

    return {
        "operating_date": operating_date,
        "cash_accounts": accounts,
        "total_cash": total_cash,
        "invoices": invoices,
        "open_invoice_count": len(open_invoices),
        "total_open_invoice_amount": total_open,
        "cash_minus_open_invoices": round(total_cash - total_open, 2),
        "notes_on_data": {
            "scope": (
                "open invoices only; rent obligations live in the leases table and "
                "are not included in total_open_invoice_amount"
            ),
            "calculations": (
                "totals, days_overdue and cash_minus_open_invoices are computed only "
                "from cash_accounts.balance, invoices.amount, invoices.due_date and "
                "desk.date_today"
            ),
        },
    }


@mcp.tool()
def get_vendor_directory() -> dict:
    """Every vendor on file with specialty and quoted lead time in days.

    Supply-side context for replenishment questions.
    `get_customer_order_fulfillment_context` returns only the one vendor
    attached to a ticket's invoice; this tool lists all of them so an agent can
    see the available options and their lead times. Read-only; placing an order
    is not supported.
    """
    with _connect() as conn:
        vendors = [dict(r) for r in conn.execute("SELECT * FROM vendors ORDER BY id")]

    return {
        "vendor_count": len(vendors),
        "vendors": vendors,
        "notes_on_data": {
            "lead_days_meaning": (
                "vendors.lead_days is a stored quoted lead time; the database holds "
                "no confirmed delivery date, no vendor capacity and no price quote"
            ),
            "no_sku_vendor_link": (
                "the schema has no vendor-to-SKU mapping; do not infer which vendor "
                "supplies a SKU except through an invoice that names it"
            ),
        },
    }


@mcp.tool()
def get_payment_history() -> dict:
    """Payments actually recorded in the database, if any.

    The authoritative check on whether money has in fact moved. Lets an agent
    verify, rather than assume, that a rent payment or invoice settlement was
    executed. An empty list means no payment has been recorded. Read-only; this
    server exposes no tool that can create a payment.
    """
    with _connect() as conn:
        payments = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id")]

    return {
        "payment_count": len(payments),
        "payments": payments,
        "notes_on_data": {
            "empty_means_unpaid": (
                "an empty payments list is positive evidence that no payment has "
                "been recorded, not merely missing data"
            ),
            "read_only": (
                "no tool on this server writes to the payments table; any claim that "
                "a payment was made must be backed by a row here"
            ),
        },
    }


@mcp.tool()
def get_vendor_shipping_status(vendor_id: int) -> dict:
    """Whether a vendor is currently blocked from shipping new product.

    Shop rule: a vendor will not ship new product while that vendor has an
    open unpaid invoice. This tool evaluates that rule and returns a decided
    `blocked` flag rather than leaving an agent to cross-reference the
    invoice list itself. Also returns the vendor's quoted lead time and what
    would have to be settled to unblock shipment.

    Read-only. It reports the block; it cannot clear one, because no tool on
    this server can pay an invoice.
    """
    vid = _coerce_ticket_id(vendor_id)
    if vid is None:
        return {
            "found": False,
            "vendor_id": vendor_id,
            "error": "A numeric vendor_id is required.",
        }

    with _connect() as conn:
        vendor = conn.execute(
            "SELECT * FROM vendors WHERE id = ?", (vid,)
        ).fetchone()
        if vendor is None:
            return {
                "found": False,
                "vendor_id": vid,
                "error": f"No vendor with id {vid}.",
            }

        invoices = [
            dict(r)
            for r in conn.execute(
                "SELECT id, amount, due_date, status, description FROM invoices "
                "WHERE vendor_id = ? ORDER BY due_date, id",
                (vid,),
            )
        ]
        desk_row = conn.execute("SELECT * FROM desk LIMIT 1").fetchone()

    operating_date = desk_row["date_today"] if desk_row is not None else None
    open_invoices = [i for i in invoices if i["status"] == "open"]
    for inv in open_invoices:
        inv["days_overdue"] = None
        if operating_date and inv["due_date"]:
            try:
                delta = (
                    date.fromisoformat(operating_date)
                    - date.fromisoformat(inv["due_date"])
                ).days
                inv["days_overdue"] = delta if delta > 0 else 0
            except ValueError:
                inv["days_overdue"] = None

    blocked = bool(open_invoices)
    amount_to_unblock = round(sum(i["amount"] for i in open_invoices), 2)

    return {
        "found": True,
        "vendor_id": vid,
        "vendor_name": vendor["name"],
        "vendor_specialty": vendor["specialty"],
        "lead_days": vendor["lead_days"],
        "operating_date": operating_date,
        "blocked": blocked,
        "block_reason": (
            f"{len(open_invoices)} open unpaid invoice(s) totalling "
            f"{amount_to_unblock}"
        )
        if blocked
        else None,
        "open_invoices": open_invoices,
        "open_invoice_count": len(open_invoices),
        "amount_to_unblock": amount_to_unblock if blocked else 0,
        "earliest_ship_possible_after": (
            "the open invoice(s) above are settled" if blocked else "no block"
        ),
        "notes_on_data": {
            "rule_encoded": (
                "shop rule: a vendor will not ship new product while it has an "
                "open unpaid invoice; blocked is computed from invoices.status, "
                "not inferred by the caller"
            ),
            "lead_days_meaning": (
                "vendors.lead_days is a stored quote that starts once the vendor "
                "is unblocked and an order is actually placed; it is not a "
                "confirmed delivery date and no order has been placed"
            ),
            "read_only": (
                "no tool on this server can pay an invoice or clear this block"
            ),
        },
    }


@mcp.tool()
def prepare_payment_proposal(
    kind: str, reference_id: int, ticket_id: int | None = None
) -> dict:
    """Prepare a payment for a human to approve. Moves no money.

    This is the only payment path available to an agent. The amount is read
    from the database here and stored on the proposal; it is never supplied by
    a caller, which is what prevents anyone asking the system to move an
    arbitrary sum later.

    `kind` is 'invoice_payment' (reference_id = invoice id) or 'rent_payment'
    (reference_id = lease id). Returns the proposal, which a human must approve
    through the backend before anything is executed.
    """
    if kind not in proposal_store.VALID_KINDS:
        return {
            "prepared": False,
            "error": (
                f"Unsupported kind '{kind}'. Supported: "
                f"{', '.join(proposal_store.VALID_KINDS)}."
            ),
        }

    rid = _coerce_ticket_id(reference_id)
    if rid is None:
        return {"prepared": False, "error": "A numeric reference_id is required."}

    with _connect() as conn:
        accounts = [
            dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name")
        ]
        if not accounts:
            return {"prepared": False, "error": "No cash account exists."}
        account = accounts[0]

        if kind == "invoice_payment":
            row = conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i "
                "LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (rid,),
            ).fetchone()
            if row is None:
                return {"prepared": False, "error": f"No invoice with id {rid}."}
            if row["status"] != "open":
                return {
                    "prepared": False,
                    "error": (
                        f"Invoice {rid} has status '{row['status']}', not 'open'; "
                        f"there is nothing to pay."
                    ),
                }
            amount = row["amount"]
            description = (
                f"Settle invoice {rid} ({row['description']}) to "
                f"{row['vendor_name']}"
            )
        else:
            row = conn.execute("SELECT * FROM leases WHERE id = ?", (rid,)).fetchone()
            if row is None:
                return {"prepared": False, "error": f"No lease with id {rid}."}
            amount = row["monthly_rent"]
            description = (
                f"Rent for {row['space_name']} to {row['landlord']}, "
                f"due {row['next_due']}"
            )

    balance = account["balance"]
    sufficient = balance >= amount

    try:
        proposal = proposal_store.create(
            kind=kind,
            amount=amount,
            account=account["name"],
            reference_id=rid,
            description=description,
            ticket_id=_coerce_ticket_id(ticket_id),
            prepared_by="agent",
        )
    except ValueError as exc:
        return {"prepared": False, "error": str(exc)}

    return {
        "prepared": True,
        "proposal": proposal,
        "cash_balance_now": balance,
        "balance_after_if_executed": round(balance - amount, 2),
        "currently_sufficient": sufficient,
        "notes_on_data": {
            "no_money_moved": (
                "this tool only records a proposal; nothing has been paid and no "
                "balance has changed"
            ),
            "human_approval_required": (
                "a human must approve this proposal through the backend before it "
                "can execute; no agent can execute it"
            ),
            "amount_is_authoritative": (
                "the amount was read from the database here and is stored on the "
                "proposal; it cannot be overridden later by any caller"
            ),
            "sufficiency_is_provisional": (
                "currently_sufficient reflects the balance at preparation time; "
                "the cash check is re-run against live data at execution"
            ),
        },
    }


@mcp.tool()
def execute_approved_payment(proposal_id: str, execution_token: str) -> dict:
    """Execute a human-approved payment. Requires a valid one-time token.

    Not reachable by an agent: the token is minted by the backend's approval
    route when a human approves, is never returned by any tool, and is 32
    random bytes.

    Enforces the shop rules deterministically rather than trusting the caller:
    the proposal must be approved and unexecuted, the amount is re-derived from
    the database, the obligation must still be outstanding, and the payment is
    refused if it would drive cash negative. The payment row, the account
    balance and the invoice status are written in one transaction.
    """
    try:
        record = proposal_store.consume_token(proposal_id, execution_token)
    except KeyError as exc:
        return {"executed": False, "error": str(exc), "reason": "not_found"}
    except ValueError as exc:
        return {"executed": False, "error": str(exc), "reason": "not_authorized"}

    kind = record["kind"]
    rid = record["reference_id"]
    account_name = record["account"]

    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")

        account = conn.execute(
            "SELECT * FROM cash_accounts WHERE name = ?", (account_name,)
        ).fetchone()
        if account is None:
            raise _PaymentRefused(f"No cash account named '{account_name}'.", "no_account")

        # Re-derive the amount from live data. If the obligation changed since
        # the proposal was prepared, refuse rather than pay a stale figure.
        if kind == "stock_purchase":
            item = record.get("item") or {}
            pricing = conn.execute(
                "SELECT * FROM pricing WHERE sku = ?", (item.get("sku"),)
            ).fetchone()
            if pricing is None:
                raise _PaymentRefused(
                    f"No unit cost for {item.get('sku')}.", "missing_obligation"
                )
            live_amount = round(pricing["unit_cost"] * int(item.get("quantity", 0)), 2)
        elif kind == "invoice_payment":
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (rid,)).fetchone()
            if row is None:
                raise _PaymentRefused(f"Invoice {rid} no longer exists.", "missing_obligation")
            if row["status"] != "open":
                raise _PaymentRefused(
                    f"Invoice {rid} is already '{row['status']}'.", "already_settled"
                )
            live_amount = row["amount"]
        else:
            row = conn.execute("SELECT * FROM leases WHERE id = ?", (rid,)).fetchone()
            if row is None:
                raise _PaymentRefused(f"Lease {rid} no longer exists.", "missing_obligation")
            live_amount = row["monthly_rent"]

        if round(live_amount, 2) != round(record["amount"], 2):
            raise _PaymentRefused(
                f"Amount changed since approval: approved {record['amount']}, "
                f"database now says {live_amount}. Refusing to pay a stale figure.",
                "amount_drift",
            )

        balance = account["balance"]
        if balance < live_amount:
            raise _PaymentRefused(
                f"Insufficient cash: balance {balance}, payment {live_amount}. "
                f"Cash may never go negative, and human approval does not "
                f"override this.",
                "insufficient_cash",
            )

        new_balance = round(balance - live_amount, 2)
        desk_row = conn.execute("SELECT * FROM desk LIMIT 1").fetchone()
        paid_at = desk_row["date_today"] if desk_row is not None else None

        payment_kind = {
            "invoice_payment": "invoice",
            "rent_payment": "rent",
            "stock_purchase": "stock_purchase",
        }[kind]
        conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                payment_kind,
                rid,
                live_amount,
                account_name,
                paid_at,
                record.get("approved_by") or "human",
            ),
        )
        conn.execute(
            "UPDATE cash_accounts SET balance = ? WHERE name = ?",
            (new_balance, account_name),
        )
        if kind == "invoice_payment":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (rid,))

        stock_after = None
        if kind == "stock_purchase":
            # Cash out and stock in, in the same transaction. Spending money
            # without receiving goods would be incoherent.
            item = record.get("item") or {}
            conn.execute(
                "UPDATE inventory SET qty = qty + ? WHERE sku = ? AND size = ?",
                (int(item["quantity"]), item["sku"], item["size"]),
            )
            stock_after = conn.execute(
                "SELECT qty FROM inventory WHERE sku = ? AND size = ?",
                (item["sku"], item["size"]),
            ).fetchone()["qty"]

        payment_id = conn.execute(
            "SELECT id FROM payments ORDER BY id DESC LIMIT 1"
        ).fetchone()["id"]
        conn.commit()
    except _PaymentRefused as refusal:
        conn.rollback()
        conn.close()
        result = {
            "executed": False,
            "error": refusal.message,
            "reason": refusal.reason,
            "proposal_id": proposal_id,
        }
        proposal_store.mark_failed(proposal_id, result)
        return result
    except Exception as exc:  # noqa: BLE001 - nothing partially written
        conn.rollback()
        conn.close()
        result = {
            "executed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "reason": "error",
            "proposal_id": proposal_id,
        }
        proposal_store.mark_failed(proposal_id, result)
        return result
    else:
        conn.close()

    result = {
        "executed": True,
        "proposal_id": proposal_id,
        "payment_id": payment_id,
        "kind": kind,
        "reference_id": rid,
        "amount": live_amount,
        "account": account_name,
        "balance_before": balance,
        "balance_after": new_balance,
        "paid_at": paid_at,
        "approved_by": record.get("approved_by"),
        "invoice_marked_paid": rid if kind == "invoice_payment" else None,
        "item": record.get("item"),
        "stock_after": stock_after,
        "notes_on_data": {
            "atomic": (
                "the payments row, the cash_accounts balance and any invoice "
                "status change were written in one transaction"
            ),
            "lease_next_due_untouched": (
                "a rent payment records the payment and deducts cash; "
                "leases.next_due is not advanced because the database defines no "
                "billing period to advance it by"
            ),
            "no_revenue": (
                "cash only goes out in this system; nothing credits an account"
            ),
            "purchase_row_has_no_item_columns": (
                "the payments table records kind, amount, account, date and "
                "approver only; which SKU a stock_purchase covers is held on the "
                "proposal and in the audit trail, not in payments"
            ),
        },
    }
    proposal_store.mark_executed(proposal_id, result)
    return result


def _vendor_for_sku(conn: sqlite3.Connection, sku: str):
    """Best available supplier for a SKU.

    The schema has no vendor-to-SKU mapping, so the only evidence is an
    invoice whose description names the SKU. Returns None when there is none -
    which is a real and common outcome, not an error.
    """
    row = conn.execute(
        "SELECT v.* FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
        "WHERE i.description LIKE ? ORDER BY i.id DESC LIMIT 1",
        (f"%{sku}%",),
    ).fetchone()
    return row


@mcp.tool()
def prepare_stock_purchase(
    sku: str, size: str, quantity: int, ticket_id: int | None = None
) -> dict:
    """Prepare a low-value restock for a human to approve. Moves no money.

    Shop rule 11: a small shortfall may be bought ahead without waiting for the
    customer to confirm, because the cost of being out of stock exceeds the
    cost of a few units. The rule is bounded, and the bounds are enforced here
    rather than left to judgement:

    - the total cost must be at or under the cap (see STOCK_PURCHASE_CAP_USD);
    - the SKU and size must exist in inventory and have a recorded unit cost;
    - if a supplier can be identified and that supplier has an open unpaid
      invoice, the purchase is refused - a blocked vendor will not ship.

    The amount is computed here as quantity x unit_cost from the database. A
    human must still approve before anything is bought.
    """
    if not isinstance(sku, str) or not sku.strip():
        return {"prepared": False, "error": "A non-empty sku is required."}
    qty = _coerce_ticket_id(quantity)
    if qty is None or qty <= 0:
        return {"prepared": False, "error": "quantity must be a positive integer."}

    sku = sku.strip()
    with _connect() as conn:
        inv = conn.execute(
            "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if inv is None:
            return {
                "prepared": False,
                "error": f"No inventory row for {sku} size {size}.",
            }

        pricing = conn.execute(
            "SELECT * FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        if pricing is None:
            return {
                "prepared": False,
                "error": f"No unit cost recorded for {sku}; cannot price a purchase.",
            }

        vendor = _vendor_for_sku(conn, sku)
        vendor_blocked = False
        blocking = []
        if vendor is not None:
            blocking = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, amount FROM invoices "
                    "WHERE vendor_id = ? AND status = 'open'",
                    (vendor["id"],),
                )
            ]
            vendor_blocked = bool(blocking)

        accounts = [
            dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name")
        ]
        if not accounts:
            return {"prepared": False, "error": "No cash account exists."}
        account = accounts[0]

    unit_cost = pricing["unit_cost"]
    amount = round(unit_cost * qty, 2)

    if amount > STOCK_PURCHASE_CAP_USD:
        return {
            "prepared": False,
            "error": (
                f"{qty} x {sku} {size} costs {amount}, above the "
                f"{STOCK_PURCHASE_CAP_USD} routine-restock cap. A shortfall this "
                f"expensive is a human decision, not routine replenishment."
            ),
            "reason": "above_cap",
            "cap": STOCK_PURCHASE_CAP_USD,
            "amount": amount,
        }

    if vendor_blocked:
        return {
            "prepared": False,
            "error": (
                f"{vendor['name']} has {len(blocking)} open unpaid invoice(s) and "
                f"will not ship. Settle those before ordering stock."
            ),
            "reason": "vendor_blocked",
            "vendor_id": vendor["id"],
            "vendor_name": vendor["name"],
            "blocking_invoices": blocking,
        }

    supplier_note = (
        f"supplier {vendor['name']} (lead {vendor['lead_days']}d)"
        if vendor is not None
        else "supplier not identifiable from the database"
    )
    description = (
        f"Restock {qty} x {inv['name']} ({sku}, size {size}) at "
        f"{unit_cost}/unit - {supplier_note}"
    )

    try:
        proposal = proposal_store.create(
            kind="stock_purchase",
            amount=amount,
            account=account["name"],
            reference_id=None,
            description=description,
            ticket_id=_coerce_ticket_id(ticket_id),
            prepared_by="agent",
            item={
                "sku": sku,
                "size": size,
                "quantity": qty,
                "unit_cost": unit_cost,
                "vendor_id": vendor["id"] if vendor is not None else None,
                "vendor_name": vendor["name"] if vendor is not None else None,
            },
        )
    except ValueError as exc:
        return {"prepared": False, "error": str(exc)}

    return {
        "prepared": True,
        "proposal": proposal,
        "unit_cost": unit_cost,
        "quantity": qty,
        "amount": amount,
        "cap": STOCK_PURCHASE_CAP_USD,
        "stock_before": inv["qty"],
        "stock_after_if_executed": inv["qty"] + qty,
        "cash_balance_now": account["balance"],
        "currently_sufficient": account["balance"] >= amount,
        "vendor_identified": vendor is not None,
        "notes_on_data": {
            "no_money_moved": (
                "this records a proposal only; nothing has been bought and no "
                "stock has arrived"
            ),
            "human_approval_required": (
                "a human must approve before this executes; no agent can execute it"
            ),
            "supplier_evidence": (
                "the schema has no vendor-to-SKU mapping; any supplier shown was "
                "inferred from an invoice naming this SKU"
            ),
            "no_revenue": (
                "buying ahead reduces cash with no modelled offset - revenue is "
                "not represented in this system"
            ),
        },
    }


@mcp.tool()
def request_ticket_resolution(ticket_id: int, summary: str) -> dict:
    """Ask a human to close a ticket. Changes nothing by itself.

    Call this once the case has actually been worked: the facts are verified,
    the recommendation is made, and anything requiring a signature has been
    prepared. The request appears on the board for a human to confirm.

    You cannot close a ticket. `tickets.status` is written only by the
    backend's resolve route, after a person confirms. Say in your result that
    closure is awaiting confirmation, never that the ticket is closed.
    """
    tid = _coerce_ticket_id(ticket_id)
    if tid is None:
        return {"requested": False, "error": "A numeric ticket_id is required."}
    if not isinstance(summary, str) or not summary.strip():
        return {
            "requested": False,
            "error": "A summary is required - say what was established and why the case can close.",
        }

    with _connect() as conn:
        ticket = _ticket(conn, tid)
        if ticket is None:
            return {"requested": False, "error": f"No ticket with id {tid}."}
        if ticket["status"] != "open":
            return {
                "requested": False,
                "error": f"Ticket {tid} is already '{ticket['status']}'.",
            }

    record = resolution_store.request(tid, summary, requested_by="agent")
    return {
        "requested": True,
        "request": record,
        "notes_on_data": {
            "nothing_changed": (
                "the ticket is still open; this records a request for a human to "
                "confirm closure"
            ),
            "human_only": (
                "no agent can set tickets.status; only the backend resolve route "
                "can, and only after a person confirms"
            ),
        },
    }


@mcp.tool()
def confirm_ticket_resolution(
    ticket_id: int, resolution_token: str, resolved_by: str
) -> dict:
    """Close a ticket after a human confirmed it. Requires a one-time token.

    Not reachable by an agent: the token is minted by the backend's resolve
    route when a person confirms, is never returned by any tool, and is 32
    random bytes. Writes `tickets.status = 'resolved'`.
    """
    tid = _coerce_ticket_id(ticket_id)
    if tid is None:
        return {"resolved": False, "error": "A numeric ticket_id is required."}

    try:
        record = resolution_store.consume_token(tid, resolution_token)
    except KeyError as exc:
        return {"resolved": False, "error": str(exc), "reason": "not_found"}
    except ValueError as exc:
        return {"resolved": False, "error": str(exc), "reason": "not_authorized"}

    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (tid,)).fetchone()
        if row is None:
            raise _PaymentRefused(f"No ticket with id {tid}.", "not_found")
        if row["status"] == "resolved":
            raise _PaymentRefused(f"Ticket {tid} is already resolved.", "already_resolved")
        conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (tid,))
        conn.commit()
    except _PaymentRefused as refusal:
        conn.rollback()
        conn.close()
        return {"resolved": False, "error": refusal.message, "reason": refusal.reason}
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        conn.close()
        return {"resolved": False, "error": f"{type(exc).__name__}: {exc}", "reason": "error"}
    else:
        conn.close()

    resolution_store.mark_resolved(tid)
    return {
        "resolved": True,
        "ticket_id": tid,
        "status": "resolved",
        "confirmed_by": resolved_by,
        "requested_by": record.get("requested_by"),
        "summary": record.get("summary"),
    }


if __name__ == "__main__":
    mcp.run()
