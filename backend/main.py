"""FastAPI layer for the Campus Customs desk (HW5 Problem 7).

    cd backend
    uvicorn main:app --reload --port 8000

This module is the HTTP surface and nothing more. It holds no SQL, no business
rules and no ticket-solving logic:

    React dashboard
      -> these routes
      -> the agent team (backend.runner) / the MCP server
      -> data/campus_customs_new.db

Shop facts are read through MCP tools, never by opening the database here.
The one mutation the system allows - executing a human-approved payment - is
also an MCP tool, called only after this layer has validated the approval.
"""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Works both as `uvicorn main:app` from inside backend/ and as
# `python -m backend.main` from the hw5 root.
_HW5_ROOT = Path(__file__).resolve().parent.parent
if str(_HW5_ROOT) not in sys.path:
    sys.path.insert(0, str(_HW5_ROOT))

from fastapi import FastAPI, HTTPException, Path as PathParam, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend import proposal_store  # noqa: E402
from backend import reset_db  # noqa: E402
from backend import resolution_store  # noqa: E402
from backend import config  # noqa: E402
from backend.agents import build_agents, build_mcp_toolset  # noqa: E402
from backend.audit import append_event  # noqa: E402
from backend.models import (  # noqa: E402
    AgentEvent,
    ApprovalRequest,
    ApprovalResult,
    CashAccount,
    CashResponse,
    EventsResponse,
    ProposalOut,
    ProposalsResponse,
    ResetResponse,
    RunOutcome,
    TicketsResponse,
    TicketSummary,
)
from backend.runner import run_ticket  # noqa: E402

# Most recent audit events returned by GET /events when no limit is given.
DEFAULT_EVENT_LIMIT = 50
# Hard ceiling, so the dashboard can never pull the whole history in one call.
MAX_EVENT_LIMIT = 500

# A ticket is "resolved" when its status is any of these. Driven by the
# database value; nothing here hard-codes which tickets are open.
RESOLVED_STATUSES = {"resolved", "closed", "done"}

# Vite's default dev server. Deliberately narrow - no wildcard origin.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hold one MCP server connection for the process rather than per request."""
    build_agents()
    toolset = build_mcp_toolset()
    async with toolset:
        app.state.mcp = toolset
        yield
    app.state.mcp = None


app = FastAPI(
    title="Campus Customs Desk API",
    version="1.0.0",
    description=(
        "Backend for the Campus Customs dashboard. Agents prepare actions; "
        "humans approve them; only then does anything change."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# --------------------------------------------------------------------- helpers


async def call_mcp(name: str, args: dict[str, Any] | None = None) -> dict:
    """Call one MCP tool and return its dict payload.

    The only route this layer has to shop data. A tool failure becomes a 502
    rather than leaking a traceback to the browser.
    """
    toolset = getattr(app.state, "mcp", None)
    if toolset is None:
        raise HTTPException(status_code=503, detail="MCP server is not connected.")
    try:
        result = await toolset.direct_call_tool(name, args or {})
    except Exception as exc:  # noqa: BLE001 - surfaced without internals
        raise HTTPException(
            status_code=502,
            detail=f"MCP tool '{name}' failed: {type(exc).__name__}.",
        ) from exc

    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"result": result}
    return {"result": result}


# ---------------------------------------------------------------------- routes


@app.get("/", tags=["meta"])
async def root() -> dict:
    """Service banner and the route list."""
    return {
        "service": "Campus Customs Desk API",
        "model": config.MODEL_NAME,
        "docs": "/docs",
        "routes": [
            "GET /tickets",
            "POST /tickets/{ticket_id}/run",
            "POST /tickets/{ticket_id}/prepare-payment",
            "POST /tickets/{ticket_id}/resolve",
            "GET /events",
            "GET /approvals",
            "POST /approvals/{proposal_id}/approve",
            "GET /cash",
            "POST /reset",
        ],
    }


@app.get("/tickets", response_model=TicketsResponse, tags=["tickets"])
async def get_tickets() -> TicketsResponse:
    """Tickets 101-103 with their live status from the database."""
    data = await call_mcp("list_open_tickets")
    rows = data.get("tickets", [])

    tickets = [
        TicketSummary(
            ticket_id=r["id"],
            type=r["type"],
            requester=r["requester"],
            subject=r["subject"],
            status=r["status"],
            is_open=r["status"] == "open",
            is_resolved=r["status"] in RESOLVED_STATUSES,
            sku=r.get("sku"),
            size=r.get("size"),
            quantity=r.get("qty"),
            lease_id=r.get("lease_id"),
            invoice_id=r.get("invoice_id"),
            created_at=r.get("created_at"),
        )
        for r in rows
    ]
    return TicketsResponse(
        operating_date=data.get("operating_date"),
        ticket_count=len(tickets),
        open_count=sum(1 for t in tickets if t.is_open),
        tickets=tickets,
    )


@app.post("/tickets/{ticket_id}/run", response_model=RunOutcome, tags=["tickets"])
async def run_ticket_route(
    ticket_id: int = PathParam(description="Ticket to hand to the agent team."),
) -> RunOutcome:
    """Run the existing agent team on one ticket.

    Delegates to `backend.runner.run_ticket`; no ticket logic lives here. The
    run may prepare a payment proposal, but it cannot approve or execute one.
    """
    data = await call_mcp("list_open_tickets")
    known = {r["id"] for r in data.get("tickets", [])}
    if ticket_id not in known:
        raise HTTPException(
            status_code=404,
            detail=f"No ticket with id {ticket_id}. Known tickets: {sorted(known)}.",
        )

    try:
        outcome = await run_ticket(ticket_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Agent run failed: {type(exc).__name__}.",
        ) from exc

    if not outcome.completed and outcome.stop_reason.startswith("error:"):
        # Surface the structured outcome rather than a 500 - the dashboard
        # should be able to show an honest failure.
        return outcome
    return outcome


@app.get("/events", response_model=EventsResponse, tags=["events"])
async def get_events(
    limit: int = Query(
        DEFAULT_EVENT_LIMIT,
        ge=1,
        le=MAX_EVENT_LIMIT,
        description=f"Most recent events to return (max {MAX_EVENT_LIMIT}).",
    ),
    ticket_id: int | None = Query(None, description="Filter to one ticket."),
) -> EventsResponse:
    """Recent agent activity from the append-only audit trail.

    The trail is written sanitized, so no key, prompt or reasoning trace can
    appear here. Returns the newest events first.
    """
    path = config.AUDIT_TRAIL_PATH
    if not path.exists():
        return EventsResponse(
            returned=0, total_available=0, limit=limit, truncated=False, events=[]
        )
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=500, detail="Audit trail could not be parsed."
        ) from exc

    if ticket_id is not None:
        records = [r for r in records if r.get("ticket_id") == ticket_id]

    total = len(records)
    window = list(reversed(records))[:limit]
    events = [AgentEvent(**{k: v for k, v in r.items() if k in AgentEvent.model_fields})
              for r in window]

    return EventsResponse(
        returned=len(events),
        total_available=total,
        limit=limit,
        truncated=total > len(events),
        events=events,
    )


@app.post(
    "/tickets/{ticket_id}/prepare-payment",
    response_model=ProposalOut,
    tags=["approvals"],
)
async def prepare_payment_for_ticket(
    ticket_id: int = PathParam(description="Ticket whose obligation to prepare."),
) -> ProposalOut:
    """Prepare the payment this ticket implies, for a human to approve.

    A deterministic path to the same proposal an agent would create. An agent
    can recommend a payment and neglect to prepare one, which leaves the
    operator holding advice with nothing to sign; this closes that gap without
    weakening any control.

    Note what the caller does *not* supply: no amount, no account, no payee.
    Only a ticket id. The obligation is resolved from the ticket, the amount is
    read from the database by the MCP tool, and the result still requires human
    approval before a cent moves.
    """
    data = await call_mcp("list_open_tickets")
    ticket = next(
        (r for r in data.get("tickets", []) if r["id"] == ticket_id), None
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"No ticket with id {ticket_id}.")

    # Which obligation does this ticket point at? Derived, never supplied.
    if ticket.get("lease_id") is not None:
        kind, reference_id = "rent_payment", ticket["lease_id"]
    elif ticket.get("invoice_id") is not None:
        kind, reference_id = "invoice_payment", ticket["invoice_id"]
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ticket {ticket_id} has no lease or invoice attached, so there "
                f"is no payable obligation to prepare."
            ),
        )

    existing = [
        p
        for p in proposal_store.list_all("pending")
        if p.get("ticket_id") == ticket_id and p.get("reference_id") == reference_id
    ]
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A payment for this obligation is already waiting for a "
                f"signature ({existing[0]['proposal_id']})."
            ),
        )

    result = await call_mcp(
        "prepare_payment_proposal",
        {"kind": kind, "reference_id": reference_id, "ticket_id": ticket_id},
    )
    if not result.get("prepared"):
        raise HTTPException(
            status_code=409,
            detail=result.get("error", "The payment could not be prepared."),
        )

    proposal = result["proposal"]
    append_event(
        run_id=f"prepare-{proposal['proposal_id']}",
        ticket_id=ticket_id,
        step=1,
        agent="harness",
        event_type="payment_prepared",
        tool_name="prepare_payment_proposal",
        arguments_summary={"kind": kind, "reference_id": reference_id},
        result_summary={
            "proposal_id": proposal["proposal_id"],
            "amount": proposal["amount"],
        },
        detail="prepared on operator request; still requires human approval",
    )

    return ProposalOut(
        **{k: v for k, v in proposal.items() if k in ProposalOut.model_fields}
    )


@app.get("/tickets/{ticket_id}/resolution-request", tags=["tickets"])
async def get_resolution_request(
    ticket_id: int = PathParam(description="Ticket to check."),
) -> dict:
    """Whether an agent has asked for this case to be closed."""
    pending = resolution_store.pending_for(ticket_id)
    return {"ticket_id": ticket_id, "pending_request": pending}


@app.post("/tickets/{ticket_id}/resolve", tags=["tickets"])
async def resolve_ticket(
    ticket_id: int = PathParam(description="Ticket to close."),
    resolved_by: str = Query("human", max_length=120),
) -> dict:
    """Close a ticket. The only path that writes `tickets.status`.

    Agents may request closure; this route is how a human grants it. It mints
    a one-time token for the write tool, so no agent can close its own case.
    """
    data = await call_mcp("list_open_tickets")
    ticket = next((r for r in data.get("tickets", []) if r["id"] == ticket_id), None)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"No ticket with id {ticket_id}.")
    if ticket["status"] == "resolved":
        raise HTTPException(
            status_code=409, detail=f"Ticket {ticket_id} is already resolved."
        )

    requested = resolution_store.pending_for(ticket_id)
    _, token = resolution_store.authorize(ticket_id, resolved_by)

    result = await call_mcp(
        "confirm_ticket_resolution",
        {
            "ticket_id": ticket_id,
            "resolution_token": token,
            "resolved_by": resolved_by,
        },
    )
    if not result.get("resolved"):
        raise HTTPException(
            status_code=409, detail=result.get("error", "Could not resolve the ticket.")
        )

    append_event(
        run_id=f"resolve-{ticket_id}",
        ticket_id=ticket_id,
        step=1,
        agent="human",
        event_type="ticket_resolved",
        tool_name="confirm_ticket_resolution",
        result_summary={
            "ticket_id": ticket_id,
            "resolved_by": resolved_by,
            "agent_requested": bool(requested),
        },
        detail=(requested or {}).get("summary"),
    )
    return result


@app.get("/approvals", response_model=ProposalsResponse, tags=["approvals"])
async def list_approvals(
    status: str | None = Query(
        None, description="pending | approved | executed | failed | voided"
    ),
) -> ProposalsResponse:
    """Prepared actions and their state. Execution tokens are never included."""
    records = proposal_store.list_all(status)
    proposals = [
        ProposalOut(**{k: v for k, v in r.items() if k in ProposalOut.model_fields})
        for r in records
    ]
    return ProposalsResponse(count=len(proposals), proposals=proposals)


@app.post(
    "/approvals/{proposal_id}/approve",
    response_model=ApprovalResult,
    tags=["approvals"],
)
async def approve_proposal(
    body: ApprovalRequest | None = None,
    proposal_id: str = PathParam(description="Id of the prepared action."),
) -> ApprovalResult:
    """Approve a prepared action and execute it.

    The caller supplies only *which* proposal and *who* approved. The amount,
    account and payee come from the stored proposal, which an agent derived
    from the database - so no caller can tell this route to move an arbitrary
    sum.

    Approval does not override the safeguards. The execution tool re-reads the
    obligation, refuses on insufficient cash, and writes the payment, the
    balance and the invoice status in one transaction.
    """
    approved_by = (body.approved_by if body else "human") or "human"

    existing = proposal_store.get(proposal_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No proposal {proposal_id}.")
    if existing["status"] == "executed":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Proposal {proposal_id} was already executed at "
                f"{existing['executed_at']}."
            ),
        )
    if existing["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal {proposal_id} is '{existing['status']}', not pending.",
        )

    try:
        proposal, token = proposal_store.approve(proposal_id, approved_by)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    append_event(
        run_id=f"approval-{proposal_id}",
        ticket_id=proposal.get("ticket_id"),
        step=1,
        agent="human",
        event_type="approval_granted",
        arguments_summary={
            "proposal_id": proposal_id,
            "kind": proposal["kind"],
            "amount": proposal["amount"],
            "approved_by": approved_by,
        },
    )

    result = await call_mcp(
        "execute_approved_payment",
        {"proposal_id": proposal_id, "execution_token": token},
    )

    append_event(
        run_id=f"approval-{proposal_id}",
        ticket_id=proposal.get("ticket_id"),
        step=2,
        agent="harness",
        event_type="payment_executed" if result.get("executed") else "payment_refused",
        tool_name="execute_approved_payment",
        result_summary={
            k: result.get(k)
            for k in ("executed", "payment_id", "amount", "balance_after", "reason")
        },
        stop_reason=result.get("reason"),
    )

    if not result.get("executed"):
        reason = result.get("reason", "error")
        status = {
            "insufficient_cash": 409,
            "already_settled": 409,
            "not_authorized": 409,
            "amount_drift": 409,
            "not_found": 404,
        }.get(reason, 500)
        raise HTTPException(
            status_code=status,
            detail=result.get("error", "Payment could not be executed."),
        )

    return ApprovalResult(
        executed=True,
        proposal_id=proposal_id,
        payment_id=result.get("payment_id"),
        amount=result.get("amount"),
        account=result.get("account"),
        balance_before=result.get("balance_before"),
        balance_after=result.get("balance_after"),
        approved_by=result.get("approved_by"),
        invoice_marked_paid=result.get("invoice_marked_paid"),
        message=(
            f"Paid {result.get('amount')} from {result.get('account')}; "
            f"balance now {result.get('balance_after')}."
        ),
    )


@app.get("/cash", response_model=CashResponse, tags=["cash"])
async def get_cash() -> CashResponse:
    """Current cash position, read live from `cash_accounts` through MCP."""
    data = await call_mcp("get_cash_position")
    accounts = [
        CashAccount(name=a["name"], balance=a["balance"], as_of=a.get("date"))
        for a in data.get("cash_accounts", [])
    ]
    checking = next((a.balance for a in accounts if a.name == "checking"), None)
    return CashResponse(
        checking_balance=checking,
        accounts=accounts,
        total_cash=data.get("total_cash", 0.0),
        open_invoice_count=data.get("open_invoice_count", 0),
        total_open_invoice_amount=data.get("total_open_invoice_amount", 0.0),
        operating_date=data.get("operating_date"),
    )


@app.post("/reset", response_model=ResetResponse, tags=["admin"])
async def reset_database() -> ResetResponse:
    """Restore the working database to its original values.

    Never touches `output/audit_trail.json` - the trail is append-only and
    keeps its evidence across runs; the reset appends a record to it instead.
    Pending proposals are voided rather than deleted, since they describe a
    world that no longer exists.
    """
    try:
        result = reset_db.reset(assume_yes=True)
    except reset_db.ResetError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Reset failed: {type(exc).__name__}."
        ) from exc

    voided = proposal_store.void_open_proposals("database reset")

    audit_count = 0
    if config.AUDIT_TRAIL_PATH.exists():
        try:
            audit_count = len(
                json.loads(config.AUDIT_TRAIL_PATH.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            audit_count = 0

    action = str(result.get("action"))
    return ResetResponse(
        action=action,
        message=(
            "Working database restored to the original baseline."
            if action == "reset"
            else "Working database was already at baseline; nothing to do."
        ),
        md5_before=result.get("working_md5"),
        md5_after=result.get("md5_after") or result.get("original_md5"),
        proposals_voided=voided,
        audit_trail_preserved=True,
        audit_record_count=audit_count,
    )
