"""Read-only open-order ownership check against durable session intents."""
from intraday_durable_fill_reconciliation import DurableFillBlocked

def inspect_open_order_ownership(orders,intents):
    if not isinstance(orders,list) or not isinstance(intents,list):
        raise DurableFillBlocked("invalid_order_ownership_snapshot")
    known={}
    for row in intents:
        if not isinstance(row,(tuple,list)) or len(row)!=3:
            raise DurableFillBlocked("invalid_durable_intent")
        client,symbol,broker_id=row
        if not isinstance(client,str) or not client.startswith("intraday-") or not isinstance(symbol,str) or not symbol or (broker_id is not None and (not isinstance(broker_id,str) or not broker_id)):
            raise DurableFillBlocked("invalid_durable_intent")
        if client in known:raise DurableFillBlocked("duplicate_durable_intent")
        known[client]=(symbol,broker_id)
    seen=set()
    owned=0
    for order in orders:
        if not isinstance(order,dict):
            raise DurableFillBlocked("invalid_open_order")
        broker_id=order.get("id")
        client=order.get("client_order_id")
        symbol=order.get("symbol")
        if not all(isinstance(x,str) and x for x in (broker_id,client,symbol)):
            raise DurableFillBlocked("invalid_open_order_identity")
        if broker_id in seen:raise DurableFillBlocked("duplicate_open_order")
        seen.add(broker_id)
        if client not in known:raise DurableFillBlocked("unattributed_open_order")
        expected_symbol,expected_id=known[client]
        if expected_symbol!=symbol or expected_id!=broker_id:
            raise DurableFillBlocked("open_order_durable_identity_mismatch")
        owned+=1
    return {"open_orders_observed":len(orders),"durably_matched_open_orders":owned,
            "open_order_identity_consistent":True,
            "account_history_complete":False,"position_attribution_certified":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
