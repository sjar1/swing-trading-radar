"""Strict, read-only ownership verification for dedicated intraday PAPER orders.

Never infer ownership from a client ID prefix alone.
"""
class OwnershipBlocked(RuntimeError):
    pass

def verify_order_ownership(open_orders, intents):
    if not isinstance(open_orders,list) or not isinstance(intents,list):
        raise OwnershipBlocked("invalid_snapshot")
    owned={}
    for intent in intents:
        if not isinstance(intent,dict):
            raise OwnershipBlocked("invalid_intent")
        client=intent.get("client_order_id")
        broker=intent.get("broker_order_id")
        symbol=intent.get("symbol")
        if not isinstance(client,str) or not client.startswith("intraday-") or not isinstance(symbol,str) or not symbol:
            raise OwnershipBlocked("incomplete_intent")
        if client in owned:
            raise OwnershipBlocked("duplicate_intent")
        owned[client]=(broker,symbol)
    seen=set()
    verified=[]
    for order in open_orders:
        if not isinstance(order,dict):
            raise OwnershipBlocked("invalid_order")
        client=order.get("client_order_id")
        broker=order.get("id")
        symbol=order.get("symbol")
        if not isinstance(client,str) or not isinstance(broker,str) or not broker or not isinstance(symbol,str):
            raise OwnershipBlocked("incomplete_order")
        if broker in seen:
            raise OwnershipBlocked("duplicate_broker_order")
        seen.add(broker)
        if client not in owned:
            raise OwnershipBlocked("untracked_broker_order")
        stored_id,stored_symbol=owned[client]
        if stored_id != broker or stored_symbol != symbol:
            raise OwnershipBlocked("broker_order_identity_mismatch")
        verified.append(broker)
    return {"verified":True,"owned_open_order_ids":verified,"broker_writes":0,"execution_enabled":False}

def verify_flatten_readiness(positions,open_orders,intents,fill_attributions):
    result=verify_order_ownership(open_orders,intents)
    if not isinstance(positions,list) or not isinstance(fill_attributions,list):
        raise OwnershipBlocked("invalid_positions_or_fills")
    if positions:
        # A complete fill-to-position ownership proof requires reconciling
        # partial fills, adjustments and bracket children, not just order IDs.
        raise OwnershipBlocked("position_fill_attribution_not_certified")
    return {**result,"no_positions":True,"cancel_plan_only":result["owned_open_order_ids"]}
