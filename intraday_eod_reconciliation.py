"""Read-only PAPER broker acknowledgement and end-of-day audit.

Never submits, cancels, replaces, or liquidates an order. Unknown ownership
or missing broker acknowledgements require human reconciliation.
"""
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo
from intraday_engine import api, PAPER
from intraday_calendar import verify_clock, CalendarBlocked

ACTIVE={"new","accepted","pending_new","partially_filled","pending_cancel",
        "pending_replace","held","accepted_for_bidding","calculated"}
FINAL={"filled","canceled","expired","rejected","replaced","done_for_day"}
KNOWN=ACTIVE|FINAL

def audit(intents, broker_orders, positions, open_orders, window):
    problems=[]
    if not isinstance(intents,list) or not isinstance(broker_orders,list) or not isinstance(positions,list) or not isinstance(open_orders,list):
        return {"verified":False,"problems":["incomplete_snapshot"],"execution_enabled":False,"orders_submitted":0}
    by_client={}
    ids=set()
    for order in broker_orders:
        if not isinstance(order,dict) or not order.get("id") or not isinstance(order.get("client_order_id"),str) or order.get("status") not in KNOWN:
            problems.append("invalid_broker_order")
            continue
        client=order["client_order_id"]
        if client in by_client or order["id"] in ids:
            problems.append("duplicate_broker_order")
        by_client[client]=order
        ids.add(order["id"])
    ledger={}
    for row in intents:
        if not isinstance(row,(tuple,list)) or len(row)!=3:
            problems.append("invalid_intent")
            continue
        key,state,broker_id=row
        if key in ledger or not isinstance(key,str) or not key.startswith("intraday-"):
            problems.append("invalid_intent_id")
        ledger[key]=(state,broker_id)
    for key,(state,broker_id) in ledger.items():
        order=by_client.get(key)
        if order is None:
            problems.append("missing_broker_acknowledgement:"+key)
        elif broker_id is not None and broker_id!=order["id"]:
            problems.append("broker_id_mismatch:"+key)
        elif state=="reserved":
            problems.append("reservation_acknowledgement_ambiguous:"+key)
        elif state=="unknown":
            problems.append("unknown_intent_state:"+key)
    for client in by_client:
        if client.startswith("intraday-") and client not in ledger:
            problems.append("untracked_intraday_order:"+client)
    if positions:
        problems.append("position_ownership_unverified")
    if window.get("flatten_due") or window.get("past_close"):
        if open_orders:
            problems.append("open_orders_at_flatten_deadline")
        if positions:
            problems.append("positions_at_flatten_deadline")
    if not isinstance(window.get("flatten_due"),bool) or not isinstance(window.get("past_close"),bool):
        problems.append("invalid_market_window")
    return {"verified":not problems,"problems":sorted(set(problems)),
            "intent_count":len(intents),"broker_order_count":len(broker_orders),
            "open_order_count":len(open_orders),"position_count":len(positions),
            "flatten_due":window.get("flatten_due",False),
            "execution_enabled":False,"orders_submitted":0,"orders_canceled":0,"positions_closed":0}

def main():
    if not all(os.getenv(k) for k in ("INTRADAY_DATABASE_URL","ALPACA_INTRADAY_API_KEY","ALPACA_INTRADAY_API_SECRET")):
        print("BLOCKED: required secrets missing")
        return 2
    try:
        import psycopg
        now=datetime.now(timezone.utc)
        ny=now.astimezone(ZoneInfo("America/New_York"))
        day=ny.date().isoformat()
        calendar=api(PAPER,"/v2/calendar?start="+day+"&end="+day)
        if not isinstance(calendar,list) or len(calendar)!=1:
            raise ValueError("calendar_missing")
        clock=api(PAPER,"/v2/clock")
        window=verify_clock(calendar[0],clock,now)
        positions=api(PAPER,"/v2/positions")
        open_orders=api(PAPER,"/v2/orders?status=open&limit=500")
        midnight=ny.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
        broker_orders=api(PAPER,"/v2/orders?status=all&limit=500&nested=false&after="+quote(midnight.isoformat()))
        if any(not isinstance(x,list) or len(x)>=500 for x in (positions,open_orders,broker_orders)):
            raise ValueError("incomplete_broker_snapshot")
        with psycopg.connect(os.environ["INTRADAY_DATABASE_URL"],connect_timeout=8,sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT client_order_id,state,broker_order_id FROM intraday_paper.order_intents WHERE session_date=%s",(day,))
                intents=cur.fetchall()
        result=audit(intents,broker_orders,positions,open_orders,window)
        print(json.dumps({"date":day,**result},sort_keys=True))
        return 0 if result["verified"] else 3
    except Exception as exc:
        print("BLOCKED: reconciliation audit failed ("+type(exc).__name__+")")
        return 3

if __name__=="__main__":
    sys.exit(main())
