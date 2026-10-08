// One payment request, rendered identically wherever it appears.
//
// The same card shows inside the open case file and in the out-tray, so the
// operator can sign from whichever one they are already looking at. Both
// render this component, so the two can never drift apart or disagree about
// what is being approved.

import { money } from "./desk";
import type { Proposal } from "./types";

interface Props {
  proposal: Proposal;
  busy: boolean;
  onApprove: (p: Proposal) => void;
  /** "inline" sits in the case file; "tray" sits in the out-tray. */
  variant?: "inline" | "tray";
  error?: string | null;
}

export function ApprovalCard({
  proposal: p,
  busy,
  onApprove,
  variant = "tray",
  error,
}: Props) {
  const kindLabel =
    p.kind === "invoice_payment"
      ? "Vendor invoice"
      : p.kind === "stock_purchase"
        ? "Stock purchase"
        : "Rent payment";
  const item = p.item ?? null;

  return (
    <div className={`request request--${variant}`}>
      <div className="request__stamp-line">
        <span className="request__pin" aria-hidden />
        Needs your signature
      </div>

      <div className="request__amount-row">
        <div>
          <div className="request__title">{kindLabel}</div>
          <p className="request__reason">{p.description}</p>
        </div>
        <div className="request__amount">
          <span className="request__amount-label">Amount</span>
          {money(p.amount)}
        </div>
      </div>

      <dl className="request__facts">
        {p.reference_id !== null && (
          <Fact
            label={p.kind === "invoice_payment" ? "Invoice" : "Lease"}
            value={`#${p.reference_id}`}
          />
        )}
        {item?.sku && (
          <Fact label="Item" value={`${item.sku} · ${item.size ?? ""}`} />
        )}
        {item?.quantity !== undefined && (
          <Fact
            label="Units"
            value={`${item.quantity} @ ${money(item.unit_cost ?? 0)}`}
          />
        )}
        <Fact label="Pay from" value={p.account} />
        {p.ticket_id !== null && <Fact label="Case" value={`#${p.ticket_id}`} />}
        <Fact label="Prepared by" value={p.prepared_by} />
      </dl>

      {error && (
        <div className="request__error">
          <strong>Not executed.</strong> {error}
        </div>
      )}

      <div className="request__actions">
        <button
          className="btn btn--approve"
          onClick={() => onApprove(p)}
          disabled={busy}
        >
          {busy ? "Processing…" : `Approve ${money(p.amount)}`}
        </button>
        <button
          className="btn btn--quiet"
          disabled
          title="Leaving it unsigned is the default — nothing happens until you approve"
        >
          Not now
        </button>
      </div>

      <p className="request__fineprint">
        The amount comes from the ledger via the backend. This desk cannot
        change it, and nothing moves until you approve.
      </p>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
