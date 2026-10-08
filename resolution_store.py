"""Ticket-resolution requests awaiting a human's confirmation.

Same control model as payments: an agent may *request* that a case be closed
and must say why, but only a human can actually close it. The agent's request
is a recommendation on the board; the write to `tickets.status` happens solely
through the backend's resolve route, which mints a one-time token the agent
has no way to obtain.

Kept separate from `proposal_store` because a resolution moves no money and
carries no amount, and conflating the two would mean loosening the amount
validation that protects payments.
"""

from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HW5_ROOT = Path(__file__).resolve().parent
STORE_PATH = HW5_ROOT / "output" / "resolution_requests.json"

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


def _public(r: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in r.items() if k != "resolution_token"}


def request(ticket_id: int, summary: str, requested_by: str = "agent") -> dict:
    """Record an agent's request that a ticket be closed. Writes nothing to the shop."""
    record = {
        "request_id": f"res-{secrets.token_hex(5)}",
        "ticket_id": ticket_id,
        "summary": summary.strip()[:600],
        "requested_by": requested_by,
        "status": "pending",
        "requested_at": _now(),
        "confirmed_at": None,
        "confirmed_by": None,
        "resolution_token": None,
    }
    with _LOCK:
        records = _read()
        # One live request per ticket; a repeat replaces the wording.
        for r in records:
            if r["ticket_id"] == ticket_id and r["status"] == "pending":
                r["summary"] = record["summary"]
                r["requested_at"] = record["requested_at"]
                _write(records)
                return _public(r)
        records.append(record)
        _write(records)
    return _public(record)


def list_all(ticket_id: int | None = None) -> list[dict[str, Any]]:
    with _LOCK:
        records = _read()
    if ticket_id is not None:
        records = [r for r in records if r["ticket_id"] == ticket_id]
    return [_public(r) for r in records]


def pending_for(ticket_id: int) -> dict[str, Any] | None:
    for r in list_all(ticket_id):
        if r["status"] == "pending":
            return r
    return None


def authorize(ticket_id: int, confirmed_by: str) -> tuple[dict[str, Any], str]:
    """Human confirmation. Mints the one-time token the write tool demands.

    A request from an agent is not required - the operator may close a case the
    agents never asked to close. What is required is that a human did this.
    """
    token = secrets.token_hex(32)
    with _LOCK:
        records = _read()
        existing = next(
            (
                r
                for r in records
                if r["ticket_id"] == ticket_id and r["status"] == "pending"
            ),
            None,
        )
        if existing is None:
            existing = {
                "request_id": f"res-{secrets.token_hex(5)}",
                "ticket_id": ticket_id,
                "summary": "Closed by the operator without an agent request.",
                "requested_by": "human",
                "status": "pending",
                "requested_at": _now(),
                "confirmed_at": None,
                "confirmed_by": None,
                "resolution_token": None,
            }
            records.append(existing)
        existing["resolution_token"] = token
        existing["confirmed_by"] = confirmed_by
        _write(records)
        return _public(existing), token


def consume_token(ticket_id: int, token: str) -> dict[str, Any]:
    """Validate and burn the token. Called only by the write tool."""
    with _LOCK:
        records = _read()
        for r in records:
            if r["ticket_id"] != ticket_id or r["status"] == "resolved":
                continue
            stored = r.get("resolution_token")
            if not stored or not token or not secrets.compare_digest(stored, token):
                raise ValueError(f"Invalid resolution token for ticket {ticket_id}.")
            r["resolution_token"] = None
            _write(records)
            return dict(r)
    raise KeyError(f"No open resolution request for ticket {ticket_id}.")


def mark_resolved(ticket_id: int) -> dict[str, Any]:
    with _LOCK:
        records = _read()
        for r in records:
            if r["ticket_id"] == ticket_id and r["status"] != "resolved":
                r["status"] = "resolved"
                r["confirmed_at"] = _now()
                r["resolution_token"] = None
                _write(records)
                return _public(r)
    raise KeyError(f"No resolution request for ticket {ticket_id}.")
