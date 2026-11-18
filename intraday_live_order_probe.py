"""Bounded read-only broker versus durable order identity probe.

Uses exact client order IDs. No broker writes, no auto retry, no execution gate.
"""
from urllib.parse import quote
from intraday_broker_recovery import decide,RecoveryBlocked
from intraday_durable_fill_reconciliation import DurableFillBlocked
from intraday_broker_fill_quantity import quantity

def inspect_orders(*,intents,api_fn,base,max_orders=20):
    if not isinstance(intents,list) or type(max_orders) is not int or not 1<=max_orders<=100 or len(intents)>max_orders:
        raise DurableFillBlocked("invalid_or_excessive_intents")
    if not callable(api_fn):
        raise DurableFillBlocked("invalid_broker_reader")
    seen=set()
    matched=0
    unresolved=0
    observed_filled_orders=0
    for row in intents:
        if not isinstance(row,(tuple,list)) or len(row)!=3:
            raise DurableFillBlocked("invalid_durable_intent")
        client,symbol,broker_id=row
        if not isinstance(client,str) or not client.startswith("intraday-") or client in seen or not isinstance(symbol,str) or not symbol:
            raise DurableFillBlocked("invalid_durable_intent")
        if broker_id is not None and (not isinstance(broker_id,str) or not broker_id):
            raise DurableFillBlocked("invalid_durable_broker_id")
        seen.add(client)
        try:
            order=api_fn(base,"/v2/orders:by_client_order_id?client_order_id="+quote(client,safe=""))
        except Exception:
            # Network failure and 404 remain ambiguous; never retry submission.
            unresolved+=1
            continue
        result=decide(client,"unknown",order)
        if not result["reconciled"]:
            unresolved+=1
            continue
        if result["broker_order_id"]!=broker_id or order.get("symbol")!=symbol:
            raise RecoveryBlocked("durable_broker_identity_mismatch")
        filled=quantity(order.get("filled_qty"))
        if filled>0:
            observed_filled_orders+=1
        matched+=1
    return {"status":"bounded_broker_order_probe","durable_intent_count":len(intents),
            "matched_broker_orders":matched,"unresolved_broker_orders":unresolved,
            "broker_orders_with_fills":observed_filled_orders,
            "broker_fill_quantity_observed":matched>0,
            "persisted_fill_quantity_compared":False,
            "broker_history_exhaustive":False,"restart_clear":False,
            "retry_submission":False,"entry_permitted":False,
            "execution_enabled":False,"broker_writes":0}
