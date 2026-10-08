// The only place the dashboard talks to the outside world.
//
// Every value shown on the desk comes through here from FastAPI. The UI never
// opens a database, never computes a balance and never decides that a payment
// succeeded - it asks the backend and renders the answer.

import type {
  ApprovalResult,
  Proposal,
  CashResponse,
  EventsResponse,
  ProposalsResponse,
  ResetResponse,
  ResolutionRequest,
  RunOutcome,
  TicketsResponse,
} from "./types";

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

/** An error carrying the backend's own explanation, not a stack trace. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const { timeoutMs = 20000, ...rest } = init ?? {};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
    });
  } catch (err) {
    clearTimeout(timer);
    if ((err as Error).name === "AbortError") {
      throw new ApiError("The office did not answer in time.", 0);
    }
    throw new ApiError("Cannot reach the operations backend.", 0);
  }
  clearTimeout(timer);

  if (!res.ok) {
    // FastAPI puts a human-readable reason in `detail`. Prefer it over a
    // generic status message so the tray can show the real refusal.
    let detail = `Request failed (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg)
        detail = body.detail[0].msg;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(detail, res.status);
  }

  return (await res.json()) as T;
}

export const api = {
  ping: () => request<{ service: string }>("/", { timeoutMs: 5000 }),

  tickets: () => request<TicketsResponse>("/tickets"),

  cash: () => request<CashResponse>("/cash"),

  events: (limit = 60, ticketId?: number) =>
    request<EventsResponse>(
      `/events?limit=${limit}` +
        (ticketId !== undefined ? `&ticket_id=${ticketId}` : ""),
    ),

  proposals: (status?: string) =>
    request<ProposalsResponse>(
      "/approvals" + (status ? `?status=${status}` : ""),
    ),

  // An agent run is a long operation - the team may make a dozen model calls.
  runTicket: (ticketId: number) =>
    request<RunOutcome>(`/tickets/${ticketId}/run`, {
      method: "POST",
      timeoutMs: 420000,
    }),

  // Takes only a ticket id. The backend resolves which obligation it means
  // and reads the amount from the database; the browser never names a figure.
  preparePayment: (ticketId: number) =>
    request<Proposal>(`/tickets/${ticketId}/prepare-payment`, {
      method: "POST",
      timeoutMs: 45000,
    }),

  // Note what is NOT sent: no amount, no account, no payee. The backend reads
  // those from the stored proposal, so this desk cannot move an arbitrary sum.
  approve: (proposalId: string, approvedBy: string) =>
    request<ApprovalResult>(`/approvals/${proposalId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by: approvedBy }),
      timeoutMs: 60000,
    }),

  resolutionRequest: (ticketId: number) =>
    request<{ ticket_id: number; pending_request: ResolutionRequest | null }>(
      `/tickets/${ticketId}/resolution-request`,
    ),

  // The only path that writes tickets.status. Human-initiated by definition:
  // an agent can request closure but has no way to call this.
  resolveTicket: (ticketId: number, resolvedBy: string) =>
    request<{ resolved: boolean; ticket_id: number }>(
      `/tickets/${ticketId}/resolve?resolved_by=${encodeURIComponent(resolvedBy)}`,
      { method: "POST", timeoutMs: 45000 },
    ),

  reset: () =>
    request<ResetResponse>("/reset", { method: "POST", timeoutMs: 60000 }),
};
