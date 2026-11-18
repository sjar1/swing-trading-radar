"""Read-only crash recovery planner for intraday PAPER orders.

A missing broker order is NOT proof that a submission failed. No broker writes.
"""
from intraday_ledger import validate_ledger, LedgerBlocked

OPEN = frozenset(("new", "accepted", "pending_new", "partially_filled",
                  "pending_cancel", "pending_replace", "held", "accepted_for_bidding"))
FINAL = frozenset(("filled", "canceled", "expired", "rejected", "replaced", "done_for_day"))
STATES = OPEN | FINAL

def recovery_plan(ledger, session_date, broker_orders, broker_positions):
    base = {"mode":"PAPER_READ_ONLY", "execution_enabled":False,
            "retry_submission":False, "safe_to_trade":False,
            "reconciled_order_ids":[], "ambiguous_keys":[]}
    try:
        validate_ledger(ledger, session_date)
    except (LedgerBlocked, TypeError, ValueError):
        return {**base, "reason":"invalid_or_missing_durable_ledger"}
    if not isinstance(broker_orders,list) or not isinstance(broker_positions,list):
        return {**base,"reason":"incomplete_broker_snapshot"}
    if broker_positions:
        return {**base,"reason":"position_attribution_unverified"}
    seen_ids=set()
    by_client={}
    for order in broker_orders:
        if not isinstance(order,dict):
            return {**base,"reason":"invalid_broker_order"}
        client=order.get("client_order_id")
        order_id=order.get("id")
        status=order.get("status")
        if not isinstance(client,str) or not client or not isinstance(order_id,str) or not order_id or status not in STATES:
            return {**base,"reason":"incomplete_broker_order"}
        if order_id in seen_ids or client in by_client:
            return {**base,"reason":"duplicate_broker_order"}
        seen_ids.add(order_id)
        by_client[client]=order
    ambiguous=[]
    matched=[]
    for key,entry in ledger["entries"].items():
        order=by_client.get(key)
        if order is None:
            # This includes a crash after submission but before broker acknowledgement.
            ambiguous.append(key)
            continue
        if entry["state"]=="reserved":
            # A reserved intent may have been submitted; broker reconciliation required.
            ambiguous.append(key)
            continue
        if entry["state"] in ("submitted","accepted","partially_filled","unknown"):
            ambiguous.append(key)
            continue
        if entry["state"] in ("filled","closed") and order["status"] not in FINAL:
            ambiguous.append(key)
            continue
        matched.append(order["id"])
    unknown_owned=[c for c in by_client if c.startswith("intraday-") and c not in ledger["entries"]]
    if unknown_owned:
        return {**base,"reason":"unrecorded_broker_orders",
                "ambiguous_keys":sorted(ambiguous+unknown_owned),
                "reconciled_order_ids":matched}
    if ambiguous:
        return {**base,"reason":"manual_reconciliation_required",
                "ambiguous_keys":sorted(ambiguous),
                "reconciled_order_ids":matched}
    return {**base,"reason":"read_only_reconciliation_complete",
            "reconciled_order_ids":matched}
