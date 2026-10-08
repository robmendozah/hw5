"""Reset the Campus Customs working database to its original baseline.

Run this before a full ticket-resolution run so each run starts from the same
world and its results are reproducible.

    python reset_db.py --check     report drift, change nothing
    python reset_db.py             reset after confirmation
    python reset_db.py --yes       reset without prompting (for scripts)

Deliberately a harness script and not an MCP tool. An agent able to reset the
database would be able to erase the evidence of its own writes, so the reset
sits outside anything the agents can reach - the same reasoning that keeps
audit logging out of their hands.

The copy only ever goes original -> working. The original is opened read-only
and is never a destination.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import uuid
from pathlib import Path

HW5 = Path(__file__).resolve().parent
sys.path.insert(0, str(HW5))

from backend.audit import append_event  # noqa: E402

ORIGINAL_DB = HW5 / "data" / "campus_customs.db"
WORKING_DB = HW5 / "data" / "campus_customs_new.db"

# MD5 of data/campus_customs.db as supplied with the homework and verified on
# 2026-10-07. The original is read-only and must never change; if this stops
# matching, the pristine source itself has been altered and copying from it
# would silently propagate the damage.
BASELINE_MD5 = "46effb90d8811f03e219ea9b5fbdfa5a"


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ResetError(RuntimeError):
    """Raised when the reset cannot be performed safely."""


def inspect() -> dict[str, object]:
    """Report the state of both databases without changing anything."""
    if not ORIGINAL_DB.exists():
        raise ResetError(f"Original database is missing: {ORIGINAL_DB}")

    original_md5 = md5(ORIGINAL_DB)
    working_exists = WORKING_DB.exists()
    working_md5 = md5(WORKING_DB) if working_exists else None

    return {
        "original_path": str(ORIGINAL_DB),
        "original_md5": original_md5,
        "original_matches_baseline": original_md5 == BASELINE_MD5,
        "working_path": str(WORKING_DB),
        "working_exists": working_exists,
        "working_md5": working_md5,
        "working_at_baseline": working_md5 == original_md5,
    }


def reset(*, assume_yes: bool = False) -> dict[str, object]:
    """Copy the original over the working database, with guards and an audit record."""
    state = inspect()

    if not state["original_matches_baseline"]:
        raise ResetError(
            "The original database does not match the recorded baseline.\n"
            f"  expected {BASELINE_MD5}\n"
            f"  found    {state['original_md5']}\n"
            "The read-only original appears to have been modified. Refusing to "
            "copy from it - restore it from the homework source first."
        )

    if state["working_at_baseline"]:
        print("Working database is already at baseline; nothing to do.")
        return {**state, "action": "no_op"}

    before_md5 = state["working_md5"]
    if not assume_yes:
        print(f"This will overwrite {WORKING_DB}")
        print(f"  current  {before_md5}")
        print(f"  baseline {state['original_md5']}")
        reply = input("Discard the working database and reset? [y/N] ").strip().lower()
        if reply not in {"y", "yes"}:
            print("Aborted; nothing was changed.")
            return {**state, "action": "aborted"}

    shutil.copy2(ORIGINAL_DB, WORKING_DB)
    after_md5 = md5(WORKING_DB)
    if after_md5 != state["original_md5"]:
        raise ResetError(
            f"Copy verification failed: working db is {after_md5}, "
            f"expected {state['original_md5']}."
        )

    # Mark the boundary in the trail so a later reader can tell where one
    # run's world ended and the next began.
    append_event(
        run_id=f"reset-{uuid.uuid4().hex[:12]}",
        ticket_id=None,
        step=1,
        agent="harness",
        event_type="database_reset",
        result_summary={
            "working_db": WORKING_DB.name,
            "md5_before": before_md5,
            "md5_after": after_md5,
        },
        detail="working database restored to the original baseline",
    )

    print(f"Reset complete. {WORKING_DB.name} restored to baseline {after_md5}.")
    return {**state, "action": "reset", "md5_after": after_md5}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="report state only, change nothing"
    )
    parser.add_argument(
        "--yes", action="store_true", help="reset without the confirmation prompt"
    )
    args = parser.parse_args(argv)

    try:
        if args.check:
            state = inspect()
            for key, value in state.items():
                print(f"{key}: {value}")
            if not state["original_matches_baseline"]:
                print("\nWARNING: the original database has drifted from baseline.")
                return 1
            if not state["working_at_baseline"]:
                print("\nWorking database has drifted; run without --check to reset.")
                return 1
            print("\nBoth databases are at baseline.")
            return 0

        result = reset(assume_yes=args.yes)
        return 0 if result["action"] in {"reset", "no_op"} else 1
    except ResetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
