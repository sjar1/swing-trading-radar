"""Single-order PAPER execution adapter: intentionally hard-disabled broker writes.

Provides an executable dry-run wiring test. The authorization path is deliberately
unimplemented until independent flattening and reconciliation are verified.
"""
import json
import os
import sys
from datetime import datetime,timezone
from decimal import Decimal
from urllib.parse import quote
from zoneinfo import ZoneInfo
from intraday_engine import api,PAPER
from intraday_calendar import verify_clock
from intraday_ledger import order_key
from intraday_paper_pilot import prepare_pilot
from intraday_pilot_preflight import evaluate

class AdapterBlocked(ValueError):
    pass

def execution_gate(*, dry_run, session_blocked, flatten_verified=False,
                   reconciliation_verified=False):
    # No configuration, workflow input, or environment variable can override this.
    if not dry_run:
        raise AdapterBlocked("broker_execution_not_implemented")
    if not session_blocked:
        raise AdapterBlocked("session_not_blocked")
    return {"execution_enabled":False,"orders_submitted":0,"mode":"PAPER_NO_SUBMIT"}

def proposal(account,positions,open_orders,history,session,intents,calendar,clock,
             symbol,trade,signal_bar,now):
    gate=execution_gate(dry_run=True,session_blocked=session is not None and session[4] is True)
    state=evaluate(account,positions,open_orders,history,session,intents,now)
    if not state["preflight_passed"]:
        raise AdapterBlocked("preflight_failed")
    window=verify_clock(calendar,clock,now)
    if not window["entry_allowed"]:
        raise AdapterBlocked("market_entry_window_closed")
    payload=prepare_pilot(symbol,trade,account,positions,open_orders,now)
    day=now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    key=order_key(day,symbol,"opening_range_breakout",signal_bar)
    risk=Decimal(payload["qty"])*(Decimal(payload["limit_price"])-Decimal(payload["stop_loss"]["stop_price"]))
    if risk<=0 or risk>25:
        raise AdapterBlocked("risk_limit")
    return {**gate,"date":day,"client_order_id":key,"symbol":symbol,
            "qty":payload["qty"],"limit_price":payload["limit_price"],
            "stop_price":payload["stop_loss"]["stop_price"],
            "target_price":payload["take_profit"]["limit_price"],
            "planned_risk":str(risk),"persisted_reservations":0,
            "broker_requests_post":0}

def main():
    if os.getenv("INTRADAY_PAPER_ORDERS")=="1":
        print("BLOCKED: execution switch cannot enable adapter")
        return 3
    required=("INTRADAY_DATABASE_URL","ALPACA_INTRADAY_API_KEY","ALPACA_INTRADAY_API_SECRET")
    if not all(os.getenv(k) for k in required):
        print("BLOCKED: credentials missing")
        return 2
    try:
        import psycopg
        now=datetime.now(timezone.utc)
        ny=now.astimezone(ZoneInfo("America/New_York"))
        day=ny.date()
        calendar=api(PAPER,"/v2/calendar?start="+day.isoformat()+"&end="+day.isoformat())
        if not isinstance(calendar,list) or len(calendar)!=1:
            raise AdapterBlocked("calendar_missing")
        clock=api(PAPER,"/v2/clock")
        account=api(PAPER,"/v2/account")
        positions=api(PAPER,"/v2/positions")
        open_orders=api(PAPER,"/v2/orders?status=open&limit=500")
        midnight=ny.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
        history=api(PAPER,"/v2/orders?status=all&limit=500&nested=false&after="+quote(midnight.isoformat()))
        if not isinstance(history,list) or len(history)>=500:
            raise AdapterBlocked("history_incomplete")
        with psycopg.connect(os.environ["INTRADAY_DATABASE_URL"],connect_timeout=8,sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT prior_close_equity,peak_equity,last_equity,drawdown,trading_blocked,revision "
                            "FROM intraday_paper.sessions WHERE session_date=%s",(day,))
                session=cur.fetchone()
                cur.execute("SELECT client_order_id FROM intraday_paper.order_intents WHERE session_date=%s",(day,))
                intents=cur.fetchall()
        # Synthetic example only: no market signal is invented or presented as actionable.
        trade={"qty":1,"limit_price":"100.00","stop_loss":{"stop_price":"99.00"},
               "take_profit":{"limit_price":"103.00"}}
        result=proposal(account,positions,open_orders,history,session,intents,calendar[0],clock,
                        "AAPL",trade,now.replace(second=0,microsecond=0).isoformat(),now)
        result["synthetic_example"]=True
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception as exc:
        print("BLOCKED: adapter dry run refused ("+(str(exc) if isinstance(exc,AdapterBlocked) else type(exc).__name__)+")")
        return 3

if __name__=="__main__":
    sys.exit(main())
