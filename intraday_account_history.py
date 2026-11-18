"""Bounded, read-only account fill history collector.

This collector establishes only that a caller-specified window was exhausted.
It never certifies account lifetime history, position ownership or trading.
"""
from datetime import datetime,timezone,timedelta
from urllib.parse import urlencode
from intraday_alpaca_fills import normalize,FillHistoryBlocked

def collect_window(*,api_fn,base,start_utc,end_utc,max_pages=20,page_size=100):
    if not isinstance(start_utc,datetime) or not isinstance(end_utc,datetime) or start_utc.tzinfo is None or end_utc.tzinfo is None:
        raise FillHistoryBlocked("invalid_window")
    if start_utc>=end_utc or end_utc>datetime.now(timezone.utc)+timedelta(minutes=5):
        raise FillHistoryBlocked("invalid_window")
    if type(max_pages)!=int or not 1<=max_pages<=50 or page_size!=100:
        raise FillHistoryBlocked("invalid_page_limits")
    # Alpaca's orders endpoint is capped at 500; a full page is not proof
    # of exhaustion, so reject it instead of silently losing older orders.
    orders=api_fn(base,"/v2/orders?"+urlencode({"status":"all","limit":500,
        "nested":"false","after":start_utc.isoformat(),"until":end_utc.isoformat()}))
    if not isinstance(orders,list) or len(orders)>=500:
        raise FillHistoryBlocked("order_history_truncated")
    activities=[]
    token=None
    seen_tokens=set()
    for _ in range(max_pages):
        query={"activity_types":"FILL","direction":"desc","page_size":page_size,
               "after":start_utc.isoformat(),"until":end_utc.isoformat()}
        if token is not None:query["page_token"]=token
        page=api_fn(base,"/v2/account/activities?"+urlencode(query))
        if not isinstance(page,list) or len(page)>page_size:
            raise FillHistoryBlocked("invalid_activity_page")
        # Reject a malformed or replayed page before accumulating it.
        page_ids=set()
        for activity in page:
            if not isinstance(activity,dict) or not isinstance(activity.get("id"),str) or not activity["id"]:
                raise FillHistoryBlocked("invalid_activity_id")
            if activity["id"] in page_ids:
                raise FillHistoryBlocked("duplicate_activity_in_page")
            page_ids.add(activity["id"])
        if page_ids.intersection({a["id"] for a in activities}):
            raise FillHistoryBlocked("duplicate_activity_across_pages")
        activities.extend(page)
        if len(page)<page_size:
            fills=normalize(activities,orders)
            return {"fills":fills,"orders_count":len(orders),
                "activity_count":len(fills),"window_exhausted":True,
                "window_start":start_utc.isoformat(),"window_end":end_utc.isoformat(),
                "account_history_complete":False,"position_attribution_certified":False,
                "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
        last=page[-1]
        if not isinstance(last,dict) or not isinstance(last.get("id"),str) or not last["id"] or last["id"] in seen_tokens:
            raise FillHistoryBlocked("repeated_or_invalid_cursor")
        token=last["id"]
        seen_tokens.add(token)
    raise FillHistoryBlocked("activity_page_limit_reached")
