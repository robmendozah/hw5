// Shared presentation helpers: the staff roster, event phrasing, formatting.
// No business logic lives here - only how backend facts are worded on the desk.

import type { AgentEvent, AgentName, DeskStatus } from "./types";

export interface StaffMember {
  id: AgentName;
  name: string;
  title: string;
  initials: string;
  accent: string;
  /** Pixel-sprite colours. Resolved hex, since SVG cannot read CSS vars here. */
  pixels: { hair: string; skin: string; shirt: string };
}

export const STAFF: StaffMember[] = [
  {
    id: "boss",
    name: "Boss",
    title: "Operations Manager",
    initials: "OM",
    accent: "var(--accent-boss)",
    pixels: { hair: "#3b3330", skin: "#d9a97f", shirt: "#6b3b43" },
  },
  {
    id: "inventory",
    name: "Inventory",
    title: "Stock & Procurement",
    initials: "SP",
    accent: "var(--accent-inventory)",
    pixels: { hair: "#6b4b2f", skin: "#e8c39b", shirt: "#54728a" },
  },
  {
    id: "accounting",
    name: "Accounting",
    title: "Finance & Controls",
    initials: "FC",
    accent: "var(--accent-accounting)",
    pixels: { hair: "#2f2a26", skin: "#a9774f", shirt: "#426a4a" },
  },
  {
    id: "facilities",
    name: "Facilities",
    title: "Lease & Premises",
    initials: "LP",
    accent: "var(--accent-facilities)",
    pixels: { hair: "#8a7256", skin: "#e6bd92", shirt: "#8a6a3f" },
  },
  {
    id: "customer_service",
    name: "Customer Service",
    title: "Customer Communications",
    initials: "CC",
    accent: "var(--accent-cs)",
    pixels: { hair: "#4a3326", skin: "#c99a68", shirt: "#4f7d7d" },
  },
];

export type StaffStatus = "idle" | "working" | "delegated" | "done" | "waiting";

export const STATUS_GLYPH: Record<StaffStatus, string> = {
  idle: "○",
  working: "●",
  delegated: "→",
  done: "✓",
  waiting: "!",
};

export const STATUS_WORD: Record<StaffStatus, string> = {
  idle: "Idle",
  working: "Working",
  delegated: "Delegated",
  done: "Done",
  waiting: "Waiting",
};

export const TICKET_TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer Order",
  rent_notice: "Rent Notice",
  price_override: "Price Override",
};

export const DESK_STATUS_LABEL: Record<DeskStatus, string> = {
  open: "Open",
  running: "Running",
  awaiting_approval: "Needs Signature",
  resolved: "Resolved",
  error: "Attention",
};

export function prettyAgent(id: string | null | undefined): string {
  if (!id) return "";
  const found = STAFF.find((s) => s.id === id);
  if (found) return found.name;
  return id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function staffFor(id: string): StaffMember | undefined {
  return STAFF.find((s) => s.id === id);
}

/** Clock-face time for the feed. Falls back to the raw value if unparseable. */
export function clockTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(11, 16);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

/** "2026-08-31" -> "Monday, Aug. 31, 2026" */
export function longDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  const s = d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  return s.replace(/^(\w+) (\w+)/, "$1, $2.");
}

export type FeedKind =
  | "delegation"
  | "tool"
  | "outcome"
  | "approval"
  | "error"
  | "system";

export interface FeedLine {
  key: string;
  time: string;
  kind: FeedKind;
  actor: string;
  target?: string;
  text: string;
  tool?: string;
  ticketId: number | null;
}

function summaryText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const parts = Object.entries(obj)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .slice(0, 4)
      .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`);
    return parts.join(" · ");
  }
  return String(value);
}

/**
 * Turn one audit record into a line of office chatter.
 *
 * Only fields the backend already sanitized are used. There is no path here
 * for chain-of-thought: the audit trail does not carry it, and this function
 * reads nothing but the named fields.
 */
export function toFeedLine(e: AgentEvent, index: number): FeedLine | null {
  const base = {
    key: `${e.run_id}-${e.step ?? index}-${e.event_type}-${index}`,
    time: clockTime(e.timestamp),
    ticketId: e.ticket_id,
  };

  switch (e.event_type) {
    case "delegation_sent": {
      const task = summaryText(e.result_summary) || taskFrom(e);
      return {
        ...base,
        kind: "delegation",
        actor: prettyAgent(e.from_agent ?? e.agent),
        target: prettyAgent(e.to_agent),
        text: task || "Asked for help on this case.",
      };
    }
    case "delegation_result":
      return {
        ...base,
        kind: "outcome",
        actor: prettyAgent(e.from_agent ?? e.agent),
        target: prettyAgent(e.to_agent),
        text: summaryText(e.result_summary) || "Reported back.",
      };
    case "delegation_refused":
    case "delegation_failed":
      return {
        ...base,
        kind: "error",
        actor: prettyAgent(e.from_agent ?? e.agent),
        target: prettyAgent(e.to_agent),
        text: e.detail || e.stop_reason || "Handoff refused.",
      };
    case "mcp_tool_call":
      return {
        ...base,
        kind: "tool",
        actor: prettyAgent(e.agent),
        tool: e.mcp_tool ?? undefined,
        text: "Pulled the file.",
      };
    case "mcp_tool_result":
      return {
        ...base,
        kind: "tool",
        actor: prettyAgent(e.agent),
        tool: e.mcp_tool ?? undefined,
        text: summaryText(e.result_summary).slice(0, 220),
      };
    case "tool_call_refused":
      return {
        ...base,
        kind: "error",
        actor: prettyAgent(e.agent),
        tool: e.mcp_tool ?? undefined,
        text: e.stop_reason ?? "Lookup refused.",
      };
    case "approval_granted":
      return {
        ...base,
        kind: "approval",
        actor: "Front Desk",
        text: `Signature given — ${summaryText(e.result_summary) || summaryText((e as unknown as { arguments_summary?: unknown }).arguments_summary) || "approval recorded"}.`,
      };
    case "payment_executed":
      return {
        ...base,
        kind: "approval",
        actor: "Accounts Payable",
        text: `Payment executed — ${summaryText(e.result_summary)}.`,
      };
    case "payment_refused":
      return {
        ...base,
        kind: "error",
        actor: "Accounts Payable",
        text: `Payment refused — ${e.stop_reason ?? summaryText(e.result_summary)}.`,
      };
    case "database_reset":
      return {
        ...base,
        kind: "system",
        actor: "Front Desk",
        text: "Morning files restored.",
      };
    case "run_started":
      return {
        ...base,
        kind: "system",
        actor: "Boss",
        text: `Opened case ${e.ticket_id ?? ""}.`.trim(),
      };
    case "run_finished":
      return {
        ...base,
        kind: e.stop_reason?.startsWith("error") ? "error" : "outcome",
        actor: "Boss",
        text: `Case closed out — ${e.stop_reason ?? "done"}.`,
      };
    default:
      return {
        ...base,
        kind: "system",
        actor: prettyAgent(e.agent),
        text: e.event_type.replace(/_/g, " "),
      };
  }
}

function taskFrom(e: AgentEvent): string {
  const args = (e as unknown as { arguments_summary?: Record<string, unknown> })
    .arguments_summary;
  if (args && typeof args.task === "string") return args.task;
  return "";
}

/**
 * Who is doing what, derived from the events of one run.
 *
 * Returns only agents the events actually mention, so the roster cannot claim
 * participation that did not happen.
 */
export function staffStatuses(
  events: AgentEvent[],
  ticketId: number | null,
  isRunning: boolean,
  involved: AgentName[] | undefined,
): Record<string, { status: StaffStatus; activity: string }> {
  const out: Record<string, { status: StaffStatus; activity: string }> = {};
  for (const s of STAFF) out[s.id] = { status: "idle", activity: "" };

  if (ticketId === null) return out;

  // Only the newest run for this ticket. Without this the roster mixes in
  // events from earlier runs of the same case and shows people "working" who
  // finished ten minutes ago.
  const forTicket = events.filter((e) => e.ticket_id === ticketId);
  const latestRunId = forTicket.find((e) => e.run_id.startsWith("run-"))?.run_id;
  const relevant = forTicket
    .filter((e) => e.run_id === latestRunId)
    .slice()
    .reverse(); // oldest first

  for (const e of relevant) {
    const agent = e.agent;
    if (!(agent in out)) continue;

    if (e.event_type === "mcp_tool_call") {
      out[agent] = {
        status: "working",
        activity: `Checking ${e.mcp_tool ?? "the files"}`,
      };
    } else if (e.event_type === "delegation_sent" && e.from_agent) {
      if (e.from_agent in out) {
        out[e.from_agent] = {
          status: "delegated",
          activity: `Waiting on ${prettyAgent(e.to_agent)}`,
        };
      }
      if (e.to_agent && e.to_agent in out) {
        out[e.to_agent] = { status: "working", activity: "Picking up the case" };
      }
    } else if (e.event_type === "delegation_result" && e.from_agent) {
      if (e.from_agent in out) {
        out[e.from_agent] = { status: "done", activity: "Reported back" };
      }
    } else if (e.event_type === "run_finished") {
      for (const id of Object.keys(out)) {
        if (out[id].status === "working" || out[id].status === "delegated") {
          out[id] = { status: "done", activity: "Finished" };
        }
      }
    }
  }

  // Once a run is over, anyone the resolution credits is Done; everyone else
  // stays Idle rather than being quietly promoted.
  if (!isRunning && involved) {
    for (const id of involved) {
      if (out[id] && out[id].status === "idle") {
        out[id] = { status: "done", activity: "Contributed to this case" };
      }
    }
  }

  return out;
}
