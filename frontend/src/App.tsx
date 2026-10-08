import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { useDesk } from "./useDesk";
import {
  DESK_STATUS_LABEL,
  STAFF,
  STATUS_GLYPH,
  STATUS_WORD,
  TICKET_TYPE_LABEL,
  longDate,
  money,
  prettyAgent,
  staffStatuses,
  toFeedLine,
} from "./desk";
import { ApprovalCard } from "./ApprovalCard";
import { PixelAgent } from "./PixelAgent";
import type { Proposal } from "./types";

export default function App() {
  const desk = useDesk();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [stamped, setStamped] = useState<Record<string, boolean>>({});
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [prepareError, setPrepareError] = useState<string | null>(null);
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const trayRef = useRef<HTMLDivElement>(null);
  const announcedRef = useRef<string | null>(null);

  // Open the first folder once the inbox arrives.
  useEffect(() => {
    if (selectedId === null && desk.tickets.length) {
      setSelectedId(desk.tickets[0].ticket_id);
    }
  }, [desk.tickets, selectedId]);

  useEffect(() => {
    if (selectedId !== null) desk.loadResolutionRequest(selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, desk.tickets]);

  const selected = desk.tickets.find((t) => t.ticket_id === selectedId) ?? null;
  const outcome = selectedId !== null ? desk.outcomes[selectedId] : undefined;
  const runError = selectedId !== null ? desk.runErrors[selectedId] : undefined;
  const isRunning = desk.runningTicketId === selectedId && selectedId !== null;

  const roster = useMemo(
    () =>
      staffStatuses(
        desk.events,
        selectedId,
        isRunning,
        outcome?.resolution?.agents_involved,
      ),
    [desk.events, selectedId, isRunning, outcome],
  );

  const feed = useMemo(
    () =>
      desk.events
        .map((e, i) => toFeedLine(e, i))
        .filter((l): l is NonNullable<typeof l> => l !== null),
    [desk.events],
  );

  const pending = desk.proposals.filter((p) => p.status === "pending");
  // Requests attached to the case currently open, so the operator can sign
  // without hunting for the tray.
  const pendingForCase = pending.filter((p) => p.ticket_id === selectedId);

  // A run can end recommending a payment without preparing one. That leaves
  // the human with advice and no way to act, so say so plainly.
  const recommendsApproval =
    outcome?.resolution?.recommendation.approval === "human_approval_required";
  const nothingToSign = recommendsApproval && pendingForCase.length === 0;

  // When a fresh request lands, bring it into view once - never repeatedly.
  useEffect(() => {
    const first = pending[0];
    if (!first) {
      announcedRef.current = null;
      return;
    }
    if (announcedRef.current === first.proposal_id) return;
    announcedRef.current = first.proposal_id;
    trayRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [pending]);

  async function handleApprove(p: Proposal) {
    setApproving(p.proposal_id);
    setApprovalError(null);
    const res = await desk.approve(p.proposal_id, "Front Desk");
    setApproving(null);
    if (res.ok) {
      // Stamp only now - after the backend confirmed the money actually moved.
      setStamped((s) => ({ ...s, [p.proposal_id]: true }));
    } else {
      setApprovalError(res.message);
    }
  }

  async function handlePrepare() {
    if (selectedId === null) return;
    setPreparing(true);
    setPrepareError(null);
    const res = await desk.preparePayment(selectedId);
    setPreparing(false);
    if (!res.ok) setPrepareError(res.message);
  }

  async function handleResolve() {
    if (selectedId === null) return;
    setResolving(true);
    setResolveError(null);
    const res = await desk.resolveTicket(selectedId, "Front Desk");
    setResolving(false);
    if (!res.ok) setResolveError(res.message);
  }

  async function handleReset() {
    setConfirmReset(false);
    setStamped({});
    setApprovalError(null);
    await desk.resetWorkday();
  }

  return (
    <div className="desk">
      {/* ------------------------------------------------ masthead */}
      <header className="masthead">
        <div className="masthead__id">
          <div className="masthead__org">CAMPUS CUSTOMS</div>
          <div className="masthead__dept">Regional Operations Desk</div>
          <div className="masthead__date">
            {longDate(desk.operatingDate) || "Loading the day…"}
          </div>
        </div>

        <div className="masthead__right">
          <div className={`ledger ${desk.cashFlash ? "ledger--changed" : ""}`}>
            <div className="ledger__label">Checking Account</div>
            <div className="ledger__sub">Available balance</div>
            <div className="ledger__amount">
              {money(desk.cash?.checking_balance)}
            </div>
            {desk.cash && desk.cash.open_invoice_count > 0 && (
              <div className="ledger__foot">
                {desk.cash.open_invoice_count} unpaid invoice
                {desk.cash.open_invoice_count === 1 ? "" : "s"} ·{" "}
                {money(desk.cash.total_open_invoice_amount)}
              </div>
            )}
          </div>

          <div className="masthead__controls">
            {pending.length > 0 && (
              <button
                className="sig-badge"
                onClick={() =>
                  trayRef.current?.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                  })
                }
              >
                <span className="sig-badge__count">{pending.length}</span>
                awaiting your signature
              </button>
            )}

            <div className={`conn conn--${desk.connectivity}`}>
              <span className="conn__dot" />
              {desk.connectivity === "online"
                ? "Line open"
                : desk.connectivity === "offline"
                  ? "Line down"
                  : "Dialling…"}
            </div>

            {confirmReset ? (
              <div className="reset-confirm">
                <span>Restore the morning files?</span>
                <button className="btn btn--danger" onClick={handleReset}>
                  Yes, reset
                </button>
                <button
                  className="btn btn--quiet"
                  onClick={() => setConfirmReset(false)}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                className="btn btn--reset"
                onClick={() => setConfirmReset(true)}
                title="Restores the database to its original values"
              >
                Reset Workday
              </button>
            )}
          </div>
        </div>
      </header>

      {desk.banner && (
        <div className={`banner banner--${desk.banner.tone}`}>
          <span>{desk.banner.text}</span>
          <button className="banner__x" onClick={desk.dismissBanner}>
            ×
          </button>
        </div>
      )}

      {desk.connectivity === "offline" && (
        <div className="offline-card">
          <h2>Office system temporarily unavailable</h2>
          <p>
            The desk cannot reach the operations backend. Start it with{" "}
            <code>uvicorn main:app --reload --port 8000</code> from the{" "}
            <code>backend/</code> folder, then try again.
          </p>
          <button className="btn" onClick={() => desk.refreshAll()}>
            Try the line again
          </button>
        </div>
      )}

      {/* ------------------------------------------------ main three columns */}
      <main className="floor">
        {/* INBOX ------------------------------------------------------- */}
        <section className="col col--inbox" aria-label="Inbox">
          <div className="tray-label">
            <span className="tray-label__tab">IN</span>
            <h2>Inbox</h2>
          </div>

          {desk.loading && <div className="skeleton-stack" aria-hidden />}

          <div className="folders">
            {desk.tickets.map((t) => {
              const status = desk.statusFor(t);
              const isSel = t.ticket_id === selectedId;
              return (
                <button
                  key={t.ticket_id}
                  className={`folder folder--${status} ${isSel ? "folder--selected" : ""}`}
                  onClick={() => setSelectedId(t.ticket_id)}
                  aria-pressed={isSel}
                >
                  <span className="folder__tab" />
                  <div className="folder__head">
                    <span className="folder__case">CASE {t.ticket_id}</span>
                    <span className={`chip chip--${status}`}>
                      {DESK_STATUS_LABEL[status]}
                    </span>
                  </div>
                  <div className="folder__type">
                    {TICKET_TYPE_LABEL[t.type] ?? t.type}
                  </div>
                  <div className="folder__party">{t.requester}</div>
                  <div className="folder__issue">{t.subject}</div>
                  {status === "resolved" && (
                    <span className="stamp stamp--resolved stamp--mini">
                      Resolved
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="sticky sticky--yellow">
            No payment without approval.
          </div>
          <div className="sticky sticky--blue">
            Vendor won’t ship with an unpaid invoice.
          </div>
        </section>

        {/* ACTIVE CASE FILE -------------------------------------------- */}
        <section className="col col--case" aria-label="Active case file">
          {!selected ? (
            <div className="case case--empty">
              <p>Pull a folder from the inbox to open it.</p>
            </div>
          ) : (
            <article className="case">
              <div className="case__header">
                <div>
                  <div className="case__no">CASE FILE #{selected.ticket_id}</div>
                  <h2 className="case__title">
                    {TICKET_TYPE_LABEL[selected.type] ?? selected.type}
                  </h2>
                </div>
                <span className={`chip chip--${desk.statusFor(selected)}`}>
                  {DESK_STATUS_LABEL[desk.statusFor(selected)]}
                </span>
              </div>

              <dl className="facts">
                <Fact label="Counterparty" value={selected.requester} />
                <Fact label="Subject" value={selected.subject} />
                <Fact label="Desk status" value={selected.status} />
                {selected.sku && <Fact label="Item" value={selected.sku} />}
                {selected.size && <Fact label="Size" value={selected.size} />}
                {selected.quantity !== null && (
                  <Fact label="Quantity" value={String(selected.quantity)} />
                )}
                {selected.invoice_id !== null && (
                  <Fact label="Invoice" value={`#${selected.invoice_id}`} />
                )}
                {selected.lease_id !== null && (
                  <Fact label="Lease" value={`#${selected.lease_id}`} />
                )}
              </dl>

              <div className="divider">
                <span>Action</span>
              </div>

              {isRunning ? (
                <div className="at-work">
                  <span className="at-work__spinner" aria-hidden />
                  <div>
                    <strong>Team at work…</strong>
                    <p>
                      The floor is handling case {selected.ticket_id}. Watch the
                      feed below.
                    </p>
                  </div>
                </div>
              ) : (
                <button
                  className="btn btn--assign"
                  onClick={() => desk.runTicket(selected.ticket_id)}
                  disabled={desk.runningTicketId !== null}
                >
                  Assign Team
                </button>
              )}

              {runError && (
                <div className="case-error">
                  <strong>The run did not complete.</strong>
                  <p>{runError}</p>
                </div>
              )}

              {/* A waiting signature belongs on the case file whether or not
                  this browser session happens to hold the run's outcome. */}
              {pendingForCase.length > 0 && (
                <>
                  <div className="divider">
                    <span>Your signature</span>
                  </div>
                  {pendingForCase.map((p) => (
                    <ApprovalCard
                      key={p.proposal_id}
                      proposal={p}
                      busy={approving === p.proposal_id}
                      onApprove={handleApprove}
                      variant="inline"
                      error={
                        approvalError && approving === null ? approvalError : null
                      }
                    />
                  ))}
                </>
              )}

              {selected && !selected.is_resolved && (
                <>
                  <div className="divider">
                    <span>Close the case</span>
                  </div>
                  {desk.resolutionRequests[selected.ticket_id] ? (
                    <div className="close-req close-req--asked">
                      <strong>The team has asked to close this case.</strong>
                      <p>
                        {desk.resolutionRequests[selected.ticket_id]?.summary}
                      </p>
                    </div>
                  ) : (
                    <p className="close-req__none">
                      No agent has asked to close this case. You can still close
                      it yourself.
                    </p>
                  )}
                  {resolveError && (
                    <div className="close-req__err">{resolveError}</div>
                  )}
                  <button
                    className="btn btn--resolve"
                    onClick={handleResolve}
                    disabled={resolving}
                  >
                    {resolving ? "Stamping…" : "Mark case resolved"}
                  </button>
                </>
              )}

              {selected?.is_resolved && (
                <div className="case-resolved">
                  <span className="stamp stamp--resolved">Resolved</span>
                  <p>
                    Closed by a human. Only the resolve route can write this
                    status — no agent can close its own case.
                  </p>
                </div>
              )}


              {outcome?.resolution && (
                <>
                  <div className="divider">
                    <span>Recommendation</span>
                  </div>
                  <p className="case__question">
                    {outcome.resolution.business_question}
                  </p>
                  <p className="case__rec">
                    {outcome.resolution.recommendation.summary}
                  </p>
                  <p className="case__rationale">
                    {outcome.resolution.recommendation.rationale}
                  </p>

                  {recommendsApproval && (
                    <div className="needs-sign-note">
                      Requires a human signature before anything is actioned.
                    </div>
                  )}

                  {nothingToSign && (
                    <div className="nothing-to-sign">
                      <strong>Nothing prepared to sign yet.</strong>
                      <p>
                        The team recommended a payment but did not draw one up,
                        so there is nothing in the tray. Prepare it here — the
                        backend reads the amount from the ledger, and it still
                        needs your signature before any money moves.
                      </p>
                      {prepareError && (
                        <p className="nothing-to-sign__err">{prepareError}</p>
                      )}
                      <button
                        className="btn btn--prepare"
                        onClick={handlePrepare}
                        disabled={preparing}
                      >
                        {preparing
                          ? "Drawing it up…"
                          : "Draw up the payment for signing"}
                      </button>
                    </div>
                  )}

                  {outcome.resolution.limitations.length > 0 && (
                    <ul className="limits">
                      {outcome.resolution.limitations.map((l, i) => (
                        <li key={i}>
                          <strong>{l.issue}</strong>
                          {l.impact ? ` — ${l.impact}` : ""}
                        </li>
                      ))}
                    </ul>
                  )}

                  {outcome.resolution.customer_message_draft && (
                    <div className="draft">
                      <div className="draft__label">
                        Draft reply — not sent
                      </div>
                      <p>{outcome.resolution.customer_message_draft}</p>
                    </div>
                  )}
                </>
              )}
            </article>
          )}
        </section>

        {/* STAFF ROOM --------------------------------------------------- */}
        <section className="col col--staff" aria-label="Staff room">
          <div className="tray-label">
            <span className="tray-label__tab">HR</span>
            <h2>Staff Room</h2>
          </div>

          <div className="roster">
            {STAFF.map((s) => {
              const st = roster[s.id];
              return (
                <div
                  key={s.id}
                  className={`nameplate nameplate--${st.status}`}
                  style={{ ["--accent" as string]: s.accent }}
                >
                  <div className="nameplate__badge">
                    <PixelAgent
                      palette={s.pixels}
                      status={st.status}
                      title={`${s.name} — ${STATUS_WORD[st.status]}`}
                    />
                    <span className="nameplate__initials">{s.initials}</span>
                  </div>
                  <div className="nameplate__body">
                    <div className="nameplate__name">{s.name}</div>
                    <div className="nameplate__title">{s.title}</div>
                    {st.activity && (
                      <div className="nameplate__activity">{st.activity}</div>
                    )}
                  </div>
                  <div className="nameplate__status" title={STATUS_WORD[st.status]}>
                    <span className={`light light--${st.status}`}>
                      {STATUS_GLYPH[st.status]}
                    </span>
                    <span className="nameplate__word">
                      {STATUS_WORD[st.status]}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="manual">
            <div className="manual__label">Desk Manual</div>
            <ol>
              <li>The shop’s today is the date on the file, not the wall clock.</li>
              <li>No payment moves without a signature.</li>
              <li>Cash never goes negative, signature or not.</li>
              <li>Customer letters stay drafts on the board.</li>
            </ol>
          </div>
        </section>
      </main>

      {/* ------------------------------------------------ live feed */}
      <section className="feed" aria-label="Live office feed">
        <div className="feed__head">
          <h2>Live Office Feed</h2>
          <span className="feed__meta">
            {feed.length} recent entries
            {desk.runningTicketId !== null && " · refreshing"}
          </span>
        </div>

        <div className="feed__sheet">
          {feed.length === 0 && (
            <p className="feed__empty">Nothing on the wire yet today.</p>
          )}
          {feed.map((l) => (
            <div key={l.key} className={`line line--${l.kind}`}>
              <span className="line__time">{l.time}</span>
              <span className="line__who">
                {l.actor}
                {l.target && <span className="line__arrow"> → {l.target}</span>}
              </span>
              <span className="line__body">
                {l.tool && <span className="tool-stamp">MCP · {l.tool}</span>}
                <span className="line__text">{l.text}</span>
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------ bottom row */}
      <section className="bottom">
        {/* APPROVAL TRAY ------------------------------------------------ */}
        <div
          className="panel panel--approvals"
          aria-label="Approval tray"
          ref={trayRef}
        >
          <div className="tray-label">
            <span className="tray-label__tab tray-label__tab--out">OUT</span>
            <h2>Approval Tray</h2>
          </div>

          {approvalError && (
            <div className="approval-error">
              <strong>Not executed.</strong>
              <p>{approvalError}</p>
            </div>
          )}

          {pending.length === 0 && (
            <p className="tray-empty">
              Nothing awaiting a signature. When the team prepares a payment it
              lands here, and in the open case file.
            </p>
          )}

          {pending.map((p) => (
            <ApprovalCard
              key={p.proposal_id}
              proposal={p}
              busy={approving === p.proposal_id}
              onApprove={handleApprove}
              variant="tray"
            />
          ))}

          {desk.proposals
            .filter((p) => p.status === "executed" && stamped[p.proposal_id])
            .map((p) => (
              <div key={p.proposal_id} className="request request--done">
                <span className="stamp stamp--approved">Approved</span>
                <div className="request__title">
                  {money(p.amount)} paid from {p.account}
                </div>
                <p className="request__reason">{p.description}</p>
              </div>
            ))}
        </div>

        {/* CASE NOTES --------------------------------------------------- */}
        <div className="panel panel--notes" aria-label="Case notes">
          <div className="tray-label">
            <span className="tray-label__tab">★</span>
            <h2>Case Notes</h2>
          </div>

          {!outcome?.resolution ? (
            <p className="tray-empty">
              Run the team on a case and the memo lands here.
            </p>
          ) : (
            <div className="memo">
              <div className="memo__clip" aria-hidden />
              <div className="memo__head">
                Agent Notes — Case #{outcome.ticket_id}
              </div>

              {outcome.resolution.agents_involved.length === 0 && (
                <p className="tray-empty">No agent contributions recorded.</p>
              )}

              {outcome.resolution.agents_involved.map((id) => (
                <div key={id} className="memo__entry">
                  <div className="memo__who">{prettyAgent(id)}</div>
                  <div className="memo__what">
                    {contributionFor(id, outcome.resolution!)}
                  </div>
                </div>
              ))}

              {outcome.resolution.verified_facts.length > 0 && (
                <div className="memo__tools">
                  <span className="memo__tools-label">Files pulled</span>
                  {[
                    ...new Set(
                      outcome.resolution.verified_facts.map((f) => f.source_tool),
                    ),
                  ].map((t) => (
                    <span key={t} className="tool-stamp">
                      {t}
                    </span>
                  ))}
                </div>
              )}

              <div className="memo__foot">
                {outcome.steps_used} steps · {outcome.delegations_used} handoffs
                · depth {outcome.max_depth_reached} · {outcome.stop_reason}
              </div>
            </div>
          )}
        </div>
      </section>

      <footer className="desk__footer">
        Campus Customs Regional Operations Desk · every figure on this board is
        read from the backend
      </footer>
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

/** A one-line account of what an agent actually did, built from its own output. */
function contributionFor(
  id: string,
  res: NonNullable<import("./types").TicketResolution>,
): string {
  const tools = [
    ...new Set(res.verified_facts.map((f) => f.source_tool)),
  ].slice(0, 2);

  if (id === "boss") {
    return `Coordinated the floor and issued the final recommendation: ${res.recommendation.summary}`;
  }
  const calc = res.calculations[0];
  if (id === "inventory") {
    return calc
      ? `Checked stock and worked the figures — ${calc.name.replace(/_/g, " ")}: ${String(calc.result)}.`
      : "Checked stock and reported availability.";
  }
  if (id === "accounting") {
    return `Reviewed the money side${tools.length ? ` using ${tools.join(" and ")}` : ""}.`;
  }
  if (id === "facilities") {
    return "Verified the lease obligation and the dates against the shop's own calendar.";
  }
  if (id === "customer_service") {
    return res.customer_message_draft
      ? "Drafted the customer reply held on the board."
      : "Advised on customer-facing wording.";
  }
  return "Contributed to this case.";
}
