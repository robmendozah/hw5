"""Append-only audit trail for the Campus Customs agent loop.

Writing here is harness behaviour, not an agent capability: no agent is given
a "write to the audit log" tool, because an agent that can choose to log can
also choose not to. Every MCP call and every delegation is recorded by the
surrounding code whether the agent cooperates or not.

The file is a JSON array on disk. Each append rewrites the array with the new
record added - existing records are never modified or removed. A corrupt or
unreadable file is set aside rather than overwritten, so history is not lost.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import AUDIT_TRAIL_PATH, OUTPUT_DIR

_LOCK = threading.Lock()


def _replace_with_retry(tmp: Path, target: Path, attempts: int = 8) -> None:
    """Atomic replace, retried.

    On Windows, a file another process holds open for reading - OneDrive sync
    being the usual culprit in this project - makes os.replace fail with
    PermissionError. It is transient, so back off briefly and retry rather
    than letting a sync client abort an agent mid-run. Observed doing exactly
    that during the Problem 9 run of ticket 103.
    """
    import time as _time

    for attempt in range(attempts):
        try:
            tmp.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            _time.sleep(0.05 * (attempt + 1))


# Short summaries keep the trail readable and keep token-heavy payloads out.
_MAX_SUMMARY_CHARS = 500

# Anything matching these is never written, regardless of where it appears.
_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|secret|password|passwd|token|authorization|bearer|credential)",
    re.IGNORECASE,
)
_REDACTED = "<redacted>"


def _secret_values() -> list[str]:
    """Live secret values to scrub, in case one reaches a summary by accident."""
    values = []
    for name in ("PORTKEY_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        v = os.getenv(name)
        if v and len(v) >= 8:
            values.append(v)
    return values


def sanitize(value: Any, _depth: int = 0) -> Any:
    """Strip secrets and truncate. Applied to everything before it is written."""
    if _depth > 6:
        return "<nested too deep>"

    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if _SECRET_KEY_PATTERN.search(str(k)):
                out[str(k)] = _REDACTED
            else:
                out[str(k)] = sanitize(v, _depth + 1)
        return out

    if isinstance(value, (list, tuple)):
        trimmed = list(value)[:20]
        result = [sanitize(v, _depth + 1) for v in trimmed]
        if len(value) > 20:
            result.append(f"<{len(value) - 20} more items omitted>")
        return result

    if isinstance(value, str):
        text = value
        for secret in _secret_values():
            text = text.replace(secret, _REDACTED)
        if _SECRET_KEY_PATTERN.search(text) and "=" in text:
            text = _SECRET_KEY_PATTERN.sub(_REDACTED, text)
        if len(text) > _MAX_SUMMARY_CHARS:
            text = text[:_MAX_SUMMARY_CHARS] + f"... <truncated, {len(value)} chars>"
        return text

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return sanitize(str(value), _depth + 1)


def _read_existing(path: Path) -> list[dict]:
    """Load the trail, preserving anything already there."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Never destroy history we cannot parse - move it aside instead.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path.rename(path.with_suffix(f".corrupt-{stamp}.json"))
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return data["records"]
    return []


def append_event(
    *,
    run_id: str,
    ticket_id: int | None,
    step: int,
    agent: str,
    event_type: str,
    from_agent: str | None = None,
    to_agent: str | None = None,
    tool_name: str | None = None,
    arguments_summary: Any = None,
    result_summary: Any = None,
    stop_reason: str | None = None,
    depth: int | None = None,
    detail: str | None = None,
) -> dict:
    """Append one record. Sanitized, never overwriting what is already there."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "ticket_id": ticket_id,
        "step": step,
        "agent": agent,
        "event_type": event_type,
    }
    if from_agent is not None:
        record["from_agent"] = from_agent
    if to_agent is not None:
        record["to_agent"] = to_agent
    if depth is not None:
        record["delegation_depth"] = depth
    if tool_name is not None:
        record["mcp_tool"] = tool_name
    if arguments_summary is not None:
        record["arguments_summary"] = sanitize(arguments_summary)
    if result_summary is not None:
        record["result_summary"] = sanitize(result_summary)
    if stop_reason is not None:
        record["stop_reason"] = stop_reason
    if detail is not None:
        record["detail"] = sanitize(detail)

    with _LOCK:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        records = _read_existing(AUDIT_TRAIL_PATH)
        records.append(record)
        tmp = AUDIT_TRAIL_PATH.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        _replace_with_retry(tmp, AUDIT_TRAIL_PATH)

    return record


def summarize_result(value: Any, limit: int = 400) -> str:
    """Compact one-line gist of a tool result, for the trail only."""
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) > limit:
        text = text[:limit] + f"... <truncated, {len(text)} chars>"
    return text
