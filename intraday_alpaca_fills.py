"""Read-only Alpaca PAPER fill activity collection and ownership mapping.

The returned data is a session diagnostic, NOT complete account history.
Never certifies fill-to-position attribution or authorizes execution.
"""
from urllib.parse import urlencode
from datetime import datetime,timezone
from intraday_engine import api,PAPER

class FillHistoryBlocked(RuntimeError):
    pass

def normalize(activities,orders):
    if not isinstance(activities,list) or not isinstance(orders,list):
        raise FillHistoryBlocked("invalid_snapshot")
    by_id={}
    for o in orders:
        if not isinstance(o,dict) or not isinstance(o.get("id"),str) or not isinstance(o.get("client_order_id"),str) or not isinstance(o.get("symbol"),str):
            raise FillHistoryBlocked("invalid_order")
        if o["id"] in by_id:raise FillHistoryBlocked("duplicate_order_id")
        by_id[o["id"]]=o
    result=[]
    seen=set()
    for a in activities:
        if not isinstance(a,dict) or a.get("activity_type")!="FILL":
            raise FillHistoryBlocked("unexpected_activity")
        aid=a.get("id")
        oid=a.get("order_id")
        if not isinstance(aid,str) or not aid or aid in seen or not isinstance(oid,str) or not oid:
            raise FillHistoryBlocked("invalid_or_duplicate_activity")
        seen.add(aid)
        order=by_id.get(oid)
        if order is None:
            raise FillHistoryBlocked("fill_order_not_in_snapshot")
        if a.get("symbol")!=order["symbol"] or a.get("side") not in ("buy","sell"):
            raise FillHistoryBlocked("fill_order_mismatch")
        result.append({"event_id":aid,"client_order_id":order["client_order_id"],
                       "symbol":a["symbol"],"side":a["side"],"qty":a.get("qty"),
                       "order_id":oid,"transaction_time":a.get("transaction_time")})
    return result

def collect_session_fills(start_utc,*,max_pages=20,page_size=100):
    if not isinstance(start_utc,datetime) or start_utc.tzinfo is None or start_utc.utcoffset()!=__import__("datetime").timedelta(0):
        raise FillHistoryBlocked("invalid_start")
    if not isinstance(max_pages,int) or isinstance(max_pages,bool) or not 1<=max_pages<=50:
        raise FillHistoryBlocked("invalid_page_limit")
    if page_size!=100:raise FillHistoryBlocked("unsupported_page_size")
    # Fetch all order records in this time window; fail closed on capped results.
    orders=api(PAPER,"/v2/orders?"+urlencode({"status":"all","limit":500,"nested":"false","after":start_utc.isoformat()}))
    if not isinstance(orders,list) or len(orders)>=500:
        raise FillHistoryBlocked("order_history_truncated")
    activities=[]
    until=None
    for _ in range(max_pages):
        query={"activity_types":"FILL","direction":"desc","page_size":page_size,
               "after":start_utc.isoformat()}
        if until:query["until"]=until
        page=api(PAPER,"/v2/account/activities?"+urlencode(query))
        if not isinstance(page,list):
            raise FillHistoryBlocked("invalid_activity_page")
        if len(page)>page_size:
            raise FillHistoryBlocked("activity_page_overflow")
        activities.extend(page)
        if len(page)<page_size:
            fills=normalize(activities,orders)
            return {"fills":fills,"activity_count":len(fills),"orders_count":len(orders),
                    "session_history_exhausted":True,"account_history_complete":False,
                    "position_attribution_certified":False,"execution_enabled":False,
                    "broker_writes":0}
        last=page[-1]
        if not isinstance(last,dict) or not isinstance(last.get("id"),str) or not last["id"] or last["id"]==until:
            raise FillHistoryBlocked("invalid_pagination_cursor")
        until=last["id"]
    raise FillHistoryBlocked("activity_page_limit_reached")
