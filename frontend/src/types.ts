// Mirrors the Pydantic response models in backend/models.py. The backend is
// the source of truth for every value here; nothing in the UI computes a
// balance, a ticket status or an agent roster for itself.

export type AgentName =
  | "boss"
  | "inventory"
  | "accounting"
  | "facilities"
  | "customer_service";

export interface Ticket {
  ticket_id: number;
  type: string;
  requester: string;
  subject: string;
  status: string;
  is_open: boolean;
  is_resolved: boolean;
  sku: string | null;
  size: string | null;
  quantity: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  created_at: string | null;
}

export interface TicketsResponse {
  operating_date: string | null;
  ticket_count: number;
  open_count: number;
  tickets: Ticket[];
}

export interface AgentEvent {
  timestamp: string;
  run_id: string;
  ticket_id: number | null;
  step: number | null;
  agent: string;
  event_type: string;
  from_agent: string | null;
  to_agent: string | null;
  delegation_depth: number | null;
  mcp_tool: string | null;
  result_summary: unknown;
  stop_reason: string | null;
  detail: string | null;
}

export interface EventsResponse {
  returned: number;
  total_available: number;
  limit: number;
  truncated: boolean;
  events: AgentEvent[];
}

export interface Proposal {
  proposal_id: string;
  kind: string;
  amount: number;
  account: string;
  reference_id: number | null;
  description: string;
  ticket_id: number | null;
  prepared_by: string;
  item: {
    sku?: string;
    size?: string;
    quantity?: number;
    unit_cost?: number;
    vendor_name?: string | null;
  } | null;
  status: string;
  created_at: string;
  approved_at: string | null;
  approved_by: string | null;
  executed_at: string | null;
  result: Record<string, unknown> | null;
}

export interface ProposalsResponse {
  count: number;
  proposals: Proposal[];
}

export interface ApprovalResult {
  executed: boolean;
  proposal_id: string;
  payment_id: number | null;
  amount: number | null;
  account: string | null;
  balance_before: number | null;
  balance_after: number | null;
  approved_by: string | null;
  invoice_marked_paid: number | null;
  message: string;
}

export interface CashAccount {
  name: string;
  balance: number;
  as_of: string | null;
}

export interface CashResponse {
  checking_balance: number | null;
  accounts: CashAccount[];
  total_cash: number;
  open_invoice_count: number;
  total_open_invoice_amount: number;
  operating_date: string | null;
}

export interface VerifiedFact {
  statement: string;
  source_tool: string;
  field: string | null;
  value: unknown;
}

export interface Calculation {
  name: string;
  inputs: Record<string, unknown>;
  result: unknown;
  formula: string | null;
}

export interface Recommendation {
  summary: string;
  rationale: string;
  confidence: number;
  approval: string;
  approval_reason: string | null;
}

export interface Limitation {
  issue: string;
  impact: string | null;
}

export interface TicketResolution {
  ticket_id: number;
  ticket_type: string | null;
  business_question: string;
  verified_facts: VerifiedFact[];
  calculations: Calculation[];
  recommendation: Recommendation;
  limitations: Limitation[];
  agents_involved: AgentName[];
  customer_message_draft: string | null;
  actions_taken: string[];
}

export interface RunOutcome {
  run_id: string;
  ticket_id: number;
  model: string;
  completed: boolean;
  stop_reason: string;
  resolution: TicketResolution | null;
  error: string | null;
  steps_used: number;
  delegations_used: number;
  max_depth_reached: number;
  started_at: string;
  finished_at: string | null;
}

export interface ResetResponse {
  action: string;
  message: string;
  md5_before: string | null;
  md5_after: string | null;
  proposals_voided: number;
  audit_trail_preserved: boolean;
  audit_record_count: number;
}

/** What the folder tab shows. Derived from backend state, never invented. */
export type DeskStatus =
  | "open"
  | "running"
  | "awaiting_approval"
  | "resolved"
  | "error";

export interface ResolutionRequest {
  request_id: string;
  ticket_id: number;
  summary: string;
  requested_by: string;
  status: string;
  requested_at: string;
  confirmed_at: string | null;
  confirmed_by: string | null;
}
