"""Shared structured contracts between the Campus Customs agents.

These models are the only vocabulary the five agents use to talk to each
other. They exist to keep four different kinds of statement apart, because
conflating them is how an agent team invents facts:

1. `VerifiedFact`    - came out of an MCP tool, with the tool named
2. `Calculation`     - arithmetic over those facts, with the inputs shown
3. `Recommendation`  - judgement, explicitly labelled as judgement
4. `Limitation`      - what could not be established

Nothing here carries chain-of-thought. A `reasoning` style free-text dump is
deliberately absent; agents report conclusions and the evidence behind them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    """The five roles. Used as both delegation target and audit identity."""

    BOSS = "boss"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    FACILITIES = "facilities"
    CUSTOMER_SERVICE = "customer_service"


class ApprovalStatus(str, Enum):
    """Whether a recommendation may be acted on without a human."""

    NOT_REQUIRED = "not_required"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"


class VerifiedFact(BaseModel):
    """One fact that came from an MCP tool call, with its provenance."""

    statement: str = Field(description="The fact, stated plainly.")
    source_tool: str = Field(
        description="Exact MCP tool name that returned it, e.g. get_cash_position."
    )
    field: str | None = Field(
        default=None, description="Field in the tool result, when it maps to one."
    )
    value: Any | None = Field(default=None, description="The raw value, if scalar.")


class Calculation(BaseModel):
    """Deterministic arithmetic over verified facts - never a judgement."""

    name: str = Field(description="What was computed, e.g. shortfall_quantity.")
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Input values the result derives from."
    )
    result: Any = Field(description="The computed value.")
    formula: str | None = Field(
        default=None, description="How it was derived, e.g. requested - on_hand."
    )


class Recommendation(BaseModel):
    """A judgement call, kept explicitly separate from facts."""

    summary: str = Field(description="The recommended course of action.")
    rationale: str = Field(description="Why, grounded in the facts above.")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="0-1 confidence in the judgement."
    )
    approval: ApprovalStatus = Field(
        default=ApprovalStatus.NOT_REQUIRED,
        description=(
            "human_approval_required for anything touching money, purchases, "
            "pricing, contracts or a customer commitment."
        ),
    )
    approval_reason: str | None = Field(
        default=None, description="Why approval is required, when it is."
    )


class Limitation(BaseModel):
    """Something that could not be established. Stated, never papered over."""

    issue: str = Field(description="What is missing or unresolved.")
    impact: str | None = Field(default=None, description="What it prevents.")


class DelegatedTask(BaseModel):
    """A focused request from one agent to another.

    Deliberately small: a question and the minimum context to answer it, never
    a conversation transcript.
    """

    from_agent: AgentName
    to_agent: AgentName
    task: str = Field(description="The focused question or task.")
    ticket_id: int | None = Field(default=None, description="Ticket under discussion.")
    context: str | None = Field(
        default=None,
        description="Facts the target needs that it cannot look up itself.",
    )
    depth: int = Field(default=0, description="Delegation depth at dispatch time.")


class AgentResult(BaseModel):
    """What every specialist returns. The same shape for all five roles."""

    agent: AgentName
    ticket_id: int | None = None
    summary: str = Field(description="Short answer to the task that was asked.")
    verified_facts: list[VerifiedFact] = Field(default_factory=list)
    calculations: list[Calculation] = Field(default_factory=list)
    recommendation: Recommendation | None = None
    limitations: list[Limitation] = Field(default_factory=list)
    consulted_agents: list[AgentName] = Field(
        default_factory=list, description="Agents this one delegated to."
    )
    tools_used: list[str] = Field(
        default_factory=list, description="MCP tools this agent called."
    )


class TicketResolution(BaseModel):
    """The Boss's final output for a ticket - what the system returns."""

    ticket_id: int
    ticket_type: str | None = None
    business_question: str = Field(description="What the ticket actually asks.")
    verified_facts: list[VerifiedFact] = Field(default_factory=list)
    calculations: list[Calculation] = Field(default_factory=list)
    recommendation: Recommendation
    limitations: list[Limitation] = Field(default_factory=list)
    agents_involved: list[AgentName] = Field(default_factory=list)
    customer_message_draft: str | None = Field(
        default=None,
        description="Drafted by Customer Service only. A draft, never sent.",
    )
    actions_taken: list[str] = Field(
        default_factory=list,
        description=(
            "Actions a tool actually performed. Expected to stay empty: every "
            "MCP tool on this server is read-only."
        ),
    )


class RunOutcome(BaseModel):
    """Envelope around a run, including how and why it stopped."""

    run_id: str
    ticket_id: int
    model: str
    completed: bool
    stop_reason: str = Field(
        description="completed | limit_reached:<which> | error:<type>"
    )
    resolution: TicketResolution | None = None
    error: str | None = None
    steps_used: int = 0
    delegations_used: int = 0
    max_depth_reached: int = 0
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: str | None = None


# --------------------------------------------------------------- API contracts
# Response shapes for the FastAPI layer (Problem 7). These wrap the agent
# models above rather than re-describing them, so the dashboard and the agent
# team cannot drift apart.


class TicketSummary(BaseModel):
    """One ticket as the dashboard board shows it."""

    ticket_id: int
    type: str
    requester: str
    subject: str
    status: str = Field(description="Live value from the database, never hard-coded.")
    is_open: bool
    is_resolved: bool
    sku: str | None = None
    size: str | None = None
    quantity: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    created_at: str | None = None


class TicketsResponse(BaseModel):
    operating_date: str | None = Field(
        default=None, description="desk.date_today - the shop's today."
    )
    ticket_count: int
    open_count: int
    tickets: list[TicketSummary]


class AgentEvent(BaseModel):
    """One sanitized row of the append-only audit trail."""

    timestamp: str
    run_id: str
    ticket_id: int | None = None
    step: int | None = None
    agent: str
    event_type: str
    from_agent: str | None = None
    to_agent: str | None = None
    delegation_depth: int | None = None
    mcp_tool: str | None = None
    result_summary: Any | None = None
    stop_reason: str | None = None
    detail: str | None = None


class EventsResponse(BaseModel):
    returned: int
    total_available: int
    limit: int
    truncated: bool = Field(
        description="True when older events exist beyond the returned window."
    )
    events: list[AgentEvent]


class ProposalOut(BaseModel):
    """A prepared action awaiting human approval. Never carries its token."""

    proposal_id: str
    kind: str
    amount: float
    account: str
    reference_id: int | None = None
    description: str
    ticket_id: int | None = None
    prepared_by: str
    item: dict[str, Any] | None = Field(
        default=None, description="sku/size/quantity for a stock_purchase."
    )
    status: str
    created_at: str
    approved_at: str | None = None
    approved_by: str | None = None
    executed_at: str | None = None
    result: dict[str, Any] | None = None


class ProposalsResponse(BaseModel):
    count: int
    proposals: list[ProposalOut]


class ApprovalRequest(BaseModel):
    """What a human may send when approving.

    Note what is absent: no amount, no account, no payee. Those come from the
    stored proposal. The caller chooses only *whether* to approve.
    """

    approved_by: str = Field(
        default="human", max_length=120, description="Who approved, for the audit row."
    )


class ApprovalResult(BaseModel):
    executed: bool
    proposal_id: str
    payment_id: int | None = None
    amount: float | None = None
    account: str | None = None
    balance_before: float | None = None
    balance_after: float | None = None
    approved_by: str | None = None
    invoice_marked_paid: int | None = None
    message: str


class CashAccount(BaseModel):
    name: str
    balance: float
    as_of: str | None = None


class CashResponse(BaseModel):
    checking_balance: float | None = Field(
        default=None, description="The checking account, which the dashboard shows."
    )
    accounts: list[CashAccount]
    total_cash: float
    open_invoice_count: int
    total_open_invoice_amount: float
    operating_date: str | None = None


class ResetResponse(BaseModel):
    action: str = Field(description="reset | no_op")
    message: str
    md5_before: str | None = None
    md5_after: str | None = None
    proposals_voided: int = 0
    audit_trail_preserved: bool = True
    audit_record_count: int = 0
