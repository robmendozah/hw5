// Desk state.
//
// The rule this file exists to enforce: the board never advances on its own.
// A ticket becomes RESOLVED because the backend said so, cash changes because
// /cash returned a new number, and an approval is stamped only after the
// approval route confirms execution. Local state tracks one thing the backend
// cannot know - that a run request is currently in flight - and nothing else.

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "./api";
import type {
  AgentEvent,
  ResolutionRequest,
  CashResponse,
  DeskStatus,
  Proposal,
  RunOutcome,
  Ticket,
} from "./types";

// Runs finish in a few seconds, so a 3s poll missed them entirely. Fast
// enough to watch the floor work, and it only runs while a run is in flight.
const POLL_MS = 1200;
const EVENT_LIMIT = 60;

export type Connectivity = "checking" | "online" | "offline";

export interface DeskState {
  tickets: Ticket[];
  operatingDate: string | null;
  cash: CashResponse | null;
  events: AgentEvent[];
  proposals: Proposal[];
  runningTicketId: number | null;
  outcomes: Record<number, RunOutcome>;
  runErrors: Record<number, string>;
  connectivity: Connectivity;
  loading: boolean;
  banner: { tone: "error" | "info"; text: string } | null;
}

export function useDesk() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [operatingDate, setOperatingDate] = useState<string | null>(null);
  const [cash, setCash] = useState<CashResponse | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [runningTicketId, setRunningTicketId] = useState<number | null>(null);
  const [outcomes, setOutcomes] = useState<Record<number, RunOutcome>>({});
  const [runErrors, setRunErrors] = useState<Record<number, string>>({});
  const [connectivity, setConnectivity] = useState<Connectivity>("checking");
  const [loading, setLoading] = useState(true);
  const [banner, setBanner] = useState<DeskState["banner"]>(null);
  const [cashFlash, setCashFlash] = useState(false);

  const prevBalance = useRef<number | null>(null);

  const note = (tone: "error" | "info", text: string) =>
    setBanner({ tone, text });

  const handle = useCallback((err: unknown, fallback: string) => {
    const msg = err instanceof ApiError ? err.message : fallback;
    if (err instanceof ApiError && err.status === 0) setConnectivity("offline");
    note("error", msg);
    return msg;
  }, []);

  // ------------------------------------------------------------- loaders

  const loadTickets = useCallback(async () => {
    const data = await api.tickets();
    setTickets(data.tickets);
    setOperatingDate(data.operating_date);
  }, []);

  const loadCash = useCallback(async () => {
    const data = await api.cash();
    const next = data.checking_balance;
    if (
      prevBalance.current !== null &&
      next !== null &&
      next !== prevBalance.current
    ) {
      setCashFlash(true);
      setTimeout(() => setCashFlash(false), 2200);
    }
    prevBalance.current = next;
    setCash(data);
  }, []);

  const loadEvents = useCallback(async () => {
    const data = await api.events(EVENT_LIMIT);
    setEvents(data.events);
  }, []);

  const loadProposals = useCallback(async () => {
    const data = await api.proposals();
    setProposals(data.proposals);
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      await Promise.all([
        loadTickets(),
        loadCash(),
        loadEvents(),
        loadProposals(),
      ]);
      setConnectivity("online");
      setBanner(null);
    } catch (err) {
      handle(err, "The office systems are not responding.");
    }
  }, [loadTickets, loadCash, loadEvents, loadProposals, handle]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await refreshAll();
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------- polling
  // Only while a run is in flight. The board is otherwise still, which is
  // both calmer to look at and kinder to the backend.

  useEffect(() => {
    if (runningTicketId === null) return;
    const id = setInterval(() => {
      loadEvents().catch(() => {
        /* a dropped poll is not worth a banner; the run result will tell */
      });
      loadProposals().catch(() => {});
    }, POLL_MS);
    return () => clearInterval(id);
  }, [runningTicketId, loadEvents, loadProposals]);

  // ------------------------------------------------------------- actions

  const runTicket = useCallback(
    async (ticketId: number) => {
      setRunningTicketId(ticketId);
      setRunErrors((e) => {
        const next = { ...e };
        delete next[ticketId];
        return next;
      });
      setBanner(null);

      // Don't wait a whole interval for the first frame of activity.
      loadEvents().catch(() => {});

      try {
        const outcome = await api.runTicket(ticketId);
        setOutcomes((o) => ({ ...o, [ticketId]: outcome }));
        // A run can finish without succeeding. Report that honestly rather
        // than letting the folder look resolved.
        if (!outcome.completed) {
          setRunErrors((e) => ({
            ...e,
            [ticketId]: outcome.error ?? outcome.stop_reason,
          }));
        }
      } catch (err) {
        const msg = handle(err, "The agent team could not be reached.");
        setRunErrors((e) => ({ ...e, [ticketId]: msg }));
      } finally {
        setRunningTicketId(null);
        await refreshAll();
      }
    },
    [handle, refreshAll],
  );

  const approve = useCallback(
    async (proposalId: string, approvedBy: string) => {
      try {
        const result = await api.approve(proposalId, approvedBy);
        await refreshAll();
        return { ok: true as const, result };
      } catch (err) {
        const msg =
          err instanceof ApiError ? err.message : "The approval did not go through.";
        // Still refresh - the backend may have recorded a refusal we should show.
        await refreshAll().catch(() => {});
        return { ok: false as const, message: msg };
      }
    },
    [refreshAll],
  );

  const preparePayment = useCallback(
    async (ticketId: number) => {
      try {
        const proposal = await api.preparePayment(ticketId);
        await loadProposals();
        return { ok: true as const, proposal };
      } catch (err) {
        const msg =
          err instanceof ApiError
            ? err.message
            : "The payment could not be prepared.";
        return { ok: false as const, message: msg };
      }
    },
    [loadProposals],
  );

  const [resolutionRequests, setResolutionRequests] = useState<
    Record<number, ResolutionRequest | null>
  >({});

  const loadResolutionRequest = useCallback(async (ticketId: number) => {
    try {
      const r = await api.resolutionRequest(ticketId);
      setResolutionRequests((m) => ({ ...m, [ticketId]: r.pending_request }));
    } catch {
      /* a missing request is not an error worth a banner */
    }
  }, []);

  const resolveTicket = useCallback(
    async (ticketId: number, resolvedBy: string) => {
      try {
        await api.resolveTicket(ticketId, resolvedBy);
        await refreshAll();
        await loadResolutionRequest(ticketId);
        return { ok: true as const };
      } catch (err) {
        const msg =
          err instanceof ApiError ? err.message : "The case could not be closed.";
        return { ok: false as const, message: msg };
      }
    },
    [refreshAll, loadResolutionRequest],
  );

  const resetWorkday = useCallback(async () => {
    try {
      const result = await api.reset();
      setOutcomes({});
      setRunErrors({});
      setRunningTicketId(null);
      prevBalance.current = null;
      await refreshAll();
      note("info", result.message);
      return { ok: true as const, result };
    } catch (err) {
      const msg = handle(err, "The workday could not be restored.");
      return { ok: false as const, message: msg };
    }
  }, [refreshAll, handle]);

  // ------------------------------------------------- derived desk status

  /** Folder-tab status. Backend first; local state only for "running". */
  const statusFor = useCallback(
    (ticket: Ticket): DeskStatus => {
      if (runningTicketId === ticket.ticket_id) return "running";
      if (runErrors[ticket.ticket_id]) return "error";
      if (ticket.is_resolved) return "resolved";
      const pending = proposals.some(
        (p) => p.ticket_id === ticket.ticket_id && p.status === "pending",
      );
      if (pending) return "awaiting_approval";
      return "open";
    },
    [runningTicketId, runErrors, proposals],
  );

  return {
    tickets,
    operatingDate,
    cash,
    cashFlash,
    events,
    proposals,
    runningTicketId,
    outcomes,
    runErrors,
    connectivity,
    loading,
    banner,
    dismissBanner: () => setBanner(null),
    runTicket,
    approve,
    preparePayment,
    resolveTicket,
    resolutionRequests,
    loadResolutionRequest,
    resetWorkday,
    refreshAll,
    statusFor,
  };
}
