"""Store for proposed payment/purchase actions awaiting human approval.

This is the record that makes "agents only prepare, humans approve" real.

An agent prepares a proposal through an MCP tool. The proposal's amount is
resolved from the database at that moment and stored here; it is never taken
from a caller. The frontend displays the proposal, a human approves it through
the FastAPI route, and only then is the action executed. Because the amount is
authoritative and stored, no caller - agent or frontend - can ask the system to
move an arbitrary sum.

Deliberately framework-free so both the MCP server and the FastAPI backend can
import it without depending on each other.

Execution tokens
----------------
Approving a proposal mints a one-time random token which the approval route
passes to the execution tool. The tool refuses without a matching token and the
token is cleared on use. An agent cannot execute a payment even for a proposal
a human has already approved: it has no way to read this file and would have to
guess 32 random bytes.
"""

from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

HW5_ROOT = Path(__file__).resolve().parent.parent
STORE_PATH = HW5_ROOT / "output" / "proposals.json"

_LOCK = threading.Lock()


def _replace_with_retry(tmp: Path, target: Path, attempts: int = 8) -> None:
    """Atomic replace, retried past transient Windows/OneDrive file locks."""
    import time as _time

    for attempt in range(attempts):
        try:
            tmp.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            _time.sleep(0.05 * (attempt + 1))


ProposalStatus = Literal["pending", "approved", "executed", "failed", "voided"]

# Kinds of action an agent may propose. Anything not listed is refused, so a
# new kind of money movement cannot be introduced by a prompt alone.
VALID_KINDS = ("invoice_payment", "rent_payment", "stock_purchase")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> list[dict[str, Any]]:
    if not STORE_PATH.exists() or STORE_PATH.stat().st_size == 0:
        return []
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        STORE_PATH.rename(STORE_PATH.with_suffix(f".corrupt-{stamp}.json"))
        return []
    return data if isinstance(data, list) else []


def _write(records: list[dict[str, Any]]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _replace_with_retry(tmp, STORE_PATH)


def _public(record: dict[str, Any]) -> dict[str, Any]:
    """A copy safe to return over HTTP - the execution token never leaves here."""
    return {k: v for k, v in record.items() if k != "execution_token"}


def create(
    *,
    kind: str,
    amount: float,
    account: str,
    reference_id: int | None,
    description: str,
    ticket_id: int | None,
    prepared_by: str,
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a proposed action. The amount must already be database-derived."""
    if kind not in VALID_KINDS:
        raise ValueError(f"Unsupported proposal kind '{kind}'.")
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("Proposal amount must be a positive number.")

    record = {
        "proposal_id": f"prop-{secrets.token_hex(6)}",
        "kind": kind,
        "amount": round(float(amount), 2),
        "account": account,
        "reference_id": reference_id,
        "description": description,
        "ticket_id": ticket_id,
        "prepared_by": prepared_by,
        # sku / size / quantity / unit_cost for a stock_purchase; None otherwise.
        "item": item,
        "status": "pending",
        "created_at": _now(),
        "approved_at": None,
        "approved_by": None,
        "executed_at": None,
        "execution_token": None,
        "result": None,
    }
    with _LOCK:
        records = _read()
        records.append(record)
        _write(records)
    return _public(record)


def list_all(status: str | None = None) -> list[dict[str, Any]]:
    with _LOCK:
        records = _read()
    if status:
        records = [r for r in records if r.get("status") == status]
    return [_public(r) for r in records]


def get(proposal_id: str) -> dict[str, Any] | None:
    with _LOCK:
        for r in _read():
            if r.get("proposal_id") == proposal_id:
                return _public(r)
    return None


def approve(proposal_id: str, approved_by: str) -> tuple[dict[str, Any], str]:
    """Mark a pending proposal approved and mint its one-time execution token.

    Raises if the proposal is missing or not pending, which is what stops the
    same action being approved - and therefore executed - twice.
    """
    with _LOCK:
        records = _read()
        for r in records:
            if r.get("proposal_id") != proposal_id:
                continue
            if r["status"] == "executed":
                raise ValueError(
                    f"Proposal {proposal_id} was already executed at "
                    f"{r['executed_at']}."
                )
            if r["status"] != "pending":
                raise ValueError(
                    f"Proposal {proposal_id} is '{r['status']}', not pending."
                )
            token = secrets.token_hex(32)
            r["status"] = "approved"
            r["approved_at"] = _now()
            r["approved_by"] = approved_by
            r["execution_token"] = token
            _write(records)
            return _public(r), token
    raise KeyError(f"No proposal with id {proposal_id}.")


def consume_token(proposal_id: str, token: str) -> dict[str, Any]:
    """Validate and burn the execution token. Called only by the execution tool.

    Returns the full authoritative record. Raises if the proposal is missing,
    not approved, already executed, or the token does not match.
    """
    with _LOCK:
        records = _read()
        for r in records:
            if r.get("proposal_id") != proposal_id:
                continue
            if r["status"] == "executed":
                raise ValueError(f"Proposal {proposal_id} was already executed.")
            if r["status"] != "approved":
                raise ValueError(
                    f"Proposal {proposal_id} is '{r['status']}'; it has not been "
                    f"approved by a human."
                )
            stored = r.get("execution_token")
            if not stored or not token or not secrets.compare_digest(stored, token):
                raise ValueError(
                    f"Invalid execution token for proposal {proposal_id}."
                )
            r["execution_token"] = None  # one-time use
            _write(records)
            return dict(r)
    raise KeyError(f"No proposal with id {proposal_id}.")


def mark_executed(proposal_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return _finish(proposal_id, "executed", result)


def mark_failed(proposal_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return _finish(proposal_id, "failed", result)


def _finish(proposal_id: str, status: ProposalStatus, result: dict) -> dict[str, Any]:
    with _LOCK:
        records = _read()
        for r in records:
            if r.get("proposal_id") == proposal_id:
                r["status"] = status
                r["result"] = result
                r["execution_token"] = None
                if status == "executed":
                    r["executed_at"] = _now()
                _write(records)
                return _public(r)
    raise KeyError(f"No proposal with id {proposal_id}.")


def void_open_proposals(reason: str) -> int:
    """Void (never delete) proposals that a database reset has made stale.

    Executed proposals are left untouched: they are evidence of what happened
    in the previous run.
    """
    voided = 0
    with _LOCK:
        records = _read()
        for r in records:
            if r.get("status") in ("pending", "approved"):
                r["status"] = "voided"
                r["execution_token"] = None
                r["result"] = {"voided_reason": reason, "voided_at": _now()}
                voided += 1
        if voided:
            _write(records)
    return voided
