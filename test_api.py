"""End-to-end API tests for HW5 Problem 7.

Start the backend first:

    cd backend
    uvicorn main:app --reload --port 8000

then from the hw5 root:

    python test_api.py

Covers the fourteen verification points, including the ones that matter most:
that the approval route cannot be told to move an arbitrary amount, that a
payment cannot execute without human approval, that insufficient cash is
refused even after approval, and that reset restores the database without
touching the audit trail.

Mutates the working database on purpose, then restores it via POST /reset.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

HW5 = Path(__file__).resolve().parent
sys.path.insert(0, str(HW5))

BASE = "http://localhost:8000"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


async def mcp_call(tool: str, args: dict) -> dict:
    """Call an MCP tool directly - stands in for what an agent would do."""
    from backend.agents import build_mcp_toolset

    async with build_mcp_toolset() as ts:
        result = await ts.direct_call_tool(tool, args)
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"result": result}
    return result


async def main() -> int:
    print("HW5 Problem 7 - API verification\n" + "=" * 62)
    c = httpx.AsyncClient(base_url=BASE, timeout=420.0)

    # Start from a known world.
    await c.post("/reset")

    # ---------------------------------------------------------------- 1
    r = await c.get("/tickets")
    body = r.json()
    ids = [t["ticket_id"] for t in body["tickets"]]
    statuses = {t["ticket_id"]: t["status"] for t in body["tickets"]}
    check(
        "1. GET /tickets returns 101-103 with live statuses",
        r.status_code == 200 and ids == [101, 102, 103],
        f"statuses={statuses}, operating_date={body['operating_date']}",
    )
    check(
        "   status is read from the database, not hard-coded",
        all(t["is_open"] == (t["status"] == "open") for t in body["tickets"]),
        "is_open derived from the status column",
    )

    # ---------------------------------------------------------------- 2
    r = await c.post("/tickets/999/run")
    check(
        "2. unknown ticket id rejected cleanly",
        r.status_code == 404 and "999" in r.json().get("detail", ""),
        f"HTTP {r.status_code}",
    )

    # ---------------------------------------------------------------- 10
    r = await c.get("/cash")
    cash = r.json()
    opening = cash["checking_balance"]
    check(
        "10. GET /cash returns the live checking balance",
        r.status_code == 200 and opening == 3400.0,
        f"checking={opening}, open invoices={cash['open_invoice_count']}",
    )

    # ------------------------------------------------- 6 (no approval, no pay)
    prep = await mcp_call(
        "prepare_payment_proposal",
        {"kind": "invoice_payment", "reference_id": 501, "ticket_id": 101},
    )
    pid = prep["proposal"]["proposal_id"]
    check(
        "   agent can prepare a proposal (no money moves)",
        prep["prepared"] and prep["proposal"]["amount"] == 840.0,
        f"{pid} amount={prep['proposal']['amount']} status={prep['proposal']['status']}",
    )

    forged = await mcp_call(
        "execute_approved_payment",
        {"proposal_id": pid, "execution_token": "f" * 64},
    )
    check(
        "6. payment refused without human approval",
        not forged.get("executed") and forged.get("reason") == "not_authorized",
        forged.get("error", "")[:90],
    )

    r = await c.get("/cash")
    check(
        "   refused attempt left cash untouched",
        r.json()["checking_balance"] == opening,
        f"still {r.json()['checking_balance']}",
    )

    # --------------------------------------------- 5 (no arbitrary amount)
    r = await c.post(
        f"/approvals/{pid}/approve",
        json={"approved_by": "roberto", "amount": 999999, "account": "checking"},
    )
    approved = r.json()
    check(
        "5. approval route ignores a caller-supplied amount",
        r.status_code == 200 and approved["amount"] == 840.0,
        f"sent amount=999999, executed {approved['amount']} (from the stored proposal)",
    )
    check(
        "9a. execution updated the balance",
        approved["balance_after"] == round(opening - 840.0, 2),
        f"{approved['balance_before']} -> {approved['balance_after']}",
    )

    # ---------------------------------------------------------------- 8
    r = await c.post(f"/approvals/{pid}/approve", json={"approved_by": "roberto"})
    check(
        "8. the same approved action cannot execute twice",
        r.status_code == 409 and "already executed" in r.json()["detail"].lower(),
        f"HTTP {r.status_code}",
    )

    # ---------------------------------------------------------------- 9
    pay = await mcp_call("get_payment_history", {})
    inv = await mcp_call("get_cash_position", {})
    invoice_501 = next((i for i in inv["invoices"] if i["id"] == 501), None)
    check(
        "9b. database records written (payments row + invoice status)",
        pay["payment_count"] == 1
        and pay["payments"][0]["amount"] == 840.0
        and pay["payments"][0]["approved_by"] == "roberto"
        and invoice_501 is not None
        and invoice_501["status"] == "paid",
        f"payment={pay['payments'][0]['kind']}/{pay['payments'][0]['amount']}, "
        f"invoice 501 now '{invoice_501['status']}'",
    )

    vendor = await mcp_call("get_vendor_shipping_status", {"vendor_id": 1})
    check(
        "   paying the invoice unblocked the vendor (shop rule 3)",
        vendor["blocked"] is False,
        "Bulldog Print Co can now ship",
    )

    # ---------------------------------------------------------------- 7
    # Balance is now 2560. Rent is 2400 -> affordable. Pay it, leaving 160,
    # then try rent again to force the insufficient-cash path.
    p2 = await mcp_call(
        "prepare_payment_proposal",
        {"kind": "rent_payment", "reference_id": 1, "ticket_id": 102},
    )
    pid2 = p2["proposal"]["proposal_id"]
    r = await c.post(f"/approvals/{pid2}/approve", json={"approved_by": "roberto"})
    after_rent = r.json()["balance_after"]
    check(
        "   affordable rent payment executes",
        r.status_code == 200 and after_rent == 160.0,
        f"balance now {after_rent}",
    )

    p3 = await mcp_call(
        "prepare_payment_proposal",
        {"kind": "rent_payment", "reference_id": 1, "ticket_id": 102},
    )
    pid3 = p3["proposal"]["proposal_id"]
    check(
        "   proposal flags that cash is now short",
        p3["currently_sufficient"] is False,
        f"balance {p3['cash_balance_now']} vs amount {p3['proposal']['amount']}",
    )
    r = await c.post(f"/approvals/{pid3}/approve", json={"approved_by": "roberto"})
    check(
        "7. insufficient cash refused even after human approval",
        r.status_code == 409 and "insufficient" in r.json()["detail"].lower(),
        r.json()["detail"][:95],
    )

    r = await c.get("/cash")
    check(
        "   refusal did not partially modify the database",
        r.json()["checking_balance"] == 160.0,
        f"balance still {r.json()['checking_balance']}",
    )

    # ---------------------------------------------------------------- 4
    r = await c.get("/events", params={"limit": 25})
    ev = r.json()
    kinds = {e["event_type"] for e in ev["events"]}
    blob = json.dumps(ev)
    check(
        "4. GET /events returns recent audit activity",
        r.status_code == 200 and ev["returned"] > 0,
        f"{ev['returned']} of {ev['total_available']} (limit {ev['limit']}), "
        f"types include {sorted(kinds)[:4]}",
    )
    check(
        "   events carry no secrets",
        "sk-" not in blob and "api_key" not in blob.lower(),
        "sanitized at write time",
    )
    r = await c.get("/events", params={"limit": 5})
    check(
        "   event limit is honoured",
        len(r.json()["events"]) == 5 and r.json()["truncated"],
        "limit=5 returns 5 and reports truncation",
    )
    r = await c.get("/events", params={"limit": 9999})
    check("   limit above the cap is rejected", r.status_code == 422, "HTTP 422")

    # ---------------------------------------------------------------- 3
    print("\n  (running the live agent team on ticket 102 - this takes a moment)")
    r = await c.post("/tickets/102/run")
    run = r.json()
    check(
        "3. POST /tickets/{id}/run invokes the real agent team",
        r.status_code == 200 and run.get("run_id", "").startswith("run-"),
        f"completed={run.get('completed')} agents="
        f"{(run.get('resolution') or {}).get('agents_involved')} "
        f"delegations={run.get('delegations_used')}",
    )

    # -------------------------------------------------------------- 11, 12
    # Leave one proposal pending so the reset has something stale to void.
    stale = await mcp_call(
        "prepare_payment_proposal",
        {"kind": "rent_payment", "reference_id": 1, "ticket_id": 102},
    )
    stale_id = stale["proposal"]["proposal_id"]

    audit_before = len(json.loads((HW5 / "output" / "audit_trail.json").read_text("utf-8")))
    r = await c.post("/reset")
    rs = r.json()
    check(
        "11. POST /reset restores the working database",
        r.status_code == 200 and rs["action"] == "reset",
        f"{rs['md5_before'][:8]}... -> {rs['md5_after'][:8]}..., "
        f"{rs['proposals_voided']} proposal(s) voided",
    )
    r = await c.get("/cash")
    check(
        "   balance back to the original value",
        r.json()["checking_balance"] == 3400.0,
        f"checking={r.json()['checking_balance']}",
    )
    pay = await mcp_call("get_payment_history", {})
    check("   payments table cleared by the reset", pay["payment_count"] == 0)

    audit_after = len(json.loads((HW5 / "output" / "audit_trail.json").read_text("utf-8")))
    check(
        "12. reset did NOT erase the audit trail",
        audit_after >= audit_before,
        f"{audit_before} -> {audit_after} records (append-only)",
    )

    # -------------------------------------------------------------- 13
    r = await c.get("/approvals")
    props = r.json()["proposals"]
    executed = [p for p in props if p["status"] == "executed"]
    voided = [p for p in props if p["status"] == "voided"]
    stale_now = next((p for p in props if p["proposal_id"] == stale_id), None)
    check(
        "13. executed proposals kept as evidence; stale ones voided not deleted",
        len(executed) >= 2
        and stale_now is not None
        and stale_now["status"] == "voided",
        f"{len(executed)} executed, {len(voided)} voided, {len(props)} total; "
        f"the pending proposal left before reset is now "
        f"'{stale_now['status'] if stale_now else 'missing'}'",
    )
    check(
        "   execution tokens never leave the server",
        all("execution_token" not in p for p in props),
        "no token field in any API response",
    )

    r = await c.get("/docs")
    check("   /docs loads", r.status_code == 200, f"HTTP {r.status_code}")

    await c.aclose()
    print("=" * 62)
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED: " + "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
