"""Independent, read-only readiness gate for a future single-order PAPER pilot.

No order submission, cancellation, session unblocking, or DB mutation.
"""
import json
import os
import sys
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote
from intraday_ledger import order_key

class PreflightBlocked(ValueError):
    pass

def evaluate(account,positions,open_orders,history,session,intents,now):
    problems=[]
    if account.get("status")!="ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
        problems.append("account_not_active")
    if not isinstance(positions,list) or positions: problems.append("positions_not_empty")
    if not isinstance(open_orders,list) or open_orders: problems.append("open_orders_not_empty")
    if not isinstance(history,list) or history: problems.append("daily_order_history_not_empty")
    if session is None: problems.append("durable_session_missing")
    else:
        prior,peak,last,drawdown,blocked,revision=session
        if blocked is not True: problems.append("session_unexpectedly_unblocked")
        if revision is None or revision<0: problems.append("invalid_revision")
        if prior is None or peak is None or last is None or drawdown is None: problems.append("invalid_equity")
        elif peak<max(prior,last) or drawdown<0: problems.append("inconsistent_equity")
    if intents: problems.append("existing_order_intents")
    if now.astimezone(ZoneInfo("America/New_York")).weekday()>=5: problems.append("not_weekday")
    return {"preflight_passed":not problems,"problems":problems,
            "execution_enabled":False,"orders_submitted":0,
            "broker_order_count":len(history) if isinstance(history,list) else None,
            "intent_count":len(intents) if isinstance(intents,list) else None}

def main():
    required=("INTRADAY_DATABASE_URL","ALPACA_INTRADAY_API_KEY","ALPACA_INTRADAY_API_SECRET")
    if not all(os.getenv(k) for k in required):
        print("BLOCKED: required secrets missing")
        return 2
    try:
        import psycopg
        from intraday_engine import api,PAPER
        now=datetime.now(timezone.utc)
        day=now.astimezone(ZoneInfo("America/New_York")).date()
        account=api(PAPER,"/v2/account")
        positions=api(PAPER,"/v2/positions")
        open_orders=api(PAPER,"/v2/orders?status=open&limit=500")
        midnight=now.astimezone(ZoneInfo("America/New_York")).replace(hour=0,minute=0,second=0,microsecond=0)
        history=api(PAPER,"/v2/orders?status=all&limit=500&nested=false&after="+quote(midnight.astimezone(timezone.utc).isoformat()))
        if not isinstance(history,list) or len(history)>=500:
            raise PreflightBlocked("broker_history_incomplete")
        with psycopg.connect(os.environ["INTRADAY_DATABASE_URL"],connect_timeout=8,sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT prior_close_equity,peak_equity,last_equity,drawdown,trading_blocked,revision "
                            "FROM intraday_paper.sessions WHERE session_date=%s",(day,))
                session=cur.fetchone()
                cur.execute("SELECT client_order_id FROM intraday_paper.order_intents WHERE session_date=%s",(day,))
                intents=cur.fetchall()
        result=evaluate(account,positions,open_orders,history,session,intents,now)
        result["date"]=day.isoformat()
        # This identifier is deterministic for the same hypothetical signal bar.
        result["sample_client_order_id"]=order_key(day.isoformat(),"AAPL","opening_range_breakout",now.replace(second=0,microsecond=0).isoformat())
        print(json.dumps(result,sort_keys=True))
        return 0 if result["preflight_passed"] else 3
    except Exception as exc:
        print("BLOCKED: pilot preflight failed ("+(str(exc) if isinstance(exc,PreflightBlocked) else type(exc).__name__)+")")
        return 3
if __name__=="__main__":
    sys.exit(main())
