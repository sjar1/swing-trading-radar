"""Read-only DB/broker open-order consistency probe. Never authorizes trading."""
from datetime import date,datetime
from intraday_durable_fill_reconciliation import load_session_intents,DurableFillBlocked
from intraday_open_order_ownership import inspect_open_order_ownership
from intraday_alpaca_fills import FillHistoryBlocked

def inspect_durable_ownership(*,db_url,session_date,api_fn,base,load_fn=load_session_intents):
    if type(session_date) is not date:
        raise DurableFillBlocked("invalid_session_date")
    if not isinstance(db_url,str) or not db_url.strip():
        raise DurableFillBlocked("missing_database_url")
    if not callable(api_fn) or not callable(load_fn):
        raise DurableFillBlocked("invalid_probe_dependencies")
    # Never read broker orders before the durable intent source is available.
    intents=load_fn(db_url,session_date.isoformat())
    if not isinstance(intents,list):
        raise DurableFillBlocked("invalid_durable_intents")
    orders=api_fn(base,"/v2/orders?status=open&limit=500&nested=false")
    if not isinstance(orders,list) or len(orders)>=500:
        raise FillHistoryBlocked("invalid_or_truncated_open_orders")
    result=inspect_open_order_ownership(orders,intents)
    return {"status":"open_orders_consistent","durable_intent_count":len(intents),
            **result,"entry_permitted":False,"execution_enabled":False,"broker_writes":0}
