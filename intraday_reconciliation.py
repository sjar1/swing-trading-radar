"""Read-only reconciliation of intraday PAPER orders and positions.

Fail closed on ambiguous order state. Does not send orders, cancel, or flatten.
"""
from datetime import datetime, timezone

PREFIX = "intraday-"
ACTIVE = frozenset(("new", "accepted", "pending_new", "partially_filled", "accepted_for_bidding", "pending_replace", "pending_cancel", "held", "calculated"))
TERMINAL = frozenset(("filled", "canceled", "expired", "rejected", "replaced", "done_for_day"))

def reconcile(orders, positions, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return {"blocked": True, "reason": "naive_timestamp"}
    if not isinstance(orders, list) or not isinstance(positions, list):
        return {"blocked": True, "reason": "invalid_broker_snapshot"}
    owned = []
    seen = set()
    for order in orders:
        if not isinstance(order, dict):
            return {"blocked": True, "reason": "invalid_order"}
        oid = order.get("id")
        client = order.get("client_order_id")
        status = order.get("status")
        if not oid or not isinstance(client, str) or not status:
            return {"blocked": True, "reason": "incomplete_order"}
        if oid in seen:
            return {"blocked": True, "reason": "duplicate_order_id"}
        seen.add(oid)
        if status not in ACTIVE | TERMINAL:
            return {"blocked": True, "reason": "unknown_order_status"}
        if client.startswith(PREFIX):
            owned.append(order)
    if positions:
        # A position snapshot cannot prove whether a given strategy owns shares.
        return {"blocked": True, "reason": "position_ownership_unverified",
                "owned_order_count": len(owned)}
    if any(o["status"] in ACTIVE for o in owned):
        return {"blocked": True, "reason": "owned_order_still_active",
                "owned_order_count": len(owned)}
    # Empty broker positions/orders still cannot establish durable idempotency.
    return {"blocked": True, "reason": "durable_execution_ledger_missing",
            "owned_order_count": len(owned), "execution_enabled": False}
