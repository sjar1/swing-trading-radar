"""Manual, fail-closed Supabase session bootstrap for dedicated Alpaca PAPER account.

Creates one BLOCKED session and one equity sample. No broker writes. No unblocking.
"""
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

def positive(value):
    if isinstance(value, bool):
        raise ValueError("invalid_equity")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid_equity")
    if not result.is_finite() or result <= 0:
        raise ValueError("invalid_equity")
    return result

def validate(account, positions, open_orders, history, now, history_complete=True):
    if not isinstance(account, dict) or account.get("status") != "ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
        raise ValueError("account_not_active")
    if not isinstance(positions, list) or positions:
        raise ValueError("positions_present_or_unreadable")
    if not isinstance(open_orders, list) or open_orders:
        raise ValueError("open_orders_present_or_unreadable")
    if not isinstance(history, list) or history or not history_complete:
        raise ValueError("today_order_history_present_or_incomplete")
    if now.tzinfo is None:
        raise ValueError("invalid_timestamp")
    current = positive(account.get("equity"))
    previous = positive(account.get("last_equity"))
    # last_equity is Alpaca's previous close, not necessarily $5,000.
    if current < previous - Decimal("0.01"):
        raise ValueError("existing_daily_loss")
    return {"date": now.astimezone(ZoneInfo("America/New_York")).date(),
            "equity": current, "prior_close": previous,
            "sampled_at": now.astimezone(timezone.utc)}

def insert_session(conn, state):
    """One transaction, no upsert. Existing sessions are never overwritten."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(461919, %s)", (int(state["date"].strftime("%Y%m%d")),))
            cur.execute("SELECT 1 FROM intraday_paper.sessions WHERE session_date=%s", (state["date"],))
            if cur.fetchone() is not None:
                raise ValueError("session_already_initialized")
            cur.execute(
                "INSERT INTO intraday_paper.sessions "
                "(session_date,prior_close_equity,peak_equity,last_equity,drawdown,trading_blocked) "
                "VALUES (%s,%s,%s,%s,0,TRUE)",
                (state["date"],state["prior_close"],max(state["prior_close"],state["equity"]),state["equity"]))
            cur.execute(
                "INSERT INTO intraday_paper.equity_samples (session_date,sampled_at,equity) "
                "VALUES (%s,%s,%s)",
                (state["date"],state["sampled_at"],state["equity"]))
    return True

def main():
    required=("INTRADAY_DATABASE_URL","ALPACA_INTRADAY_API_KEY","ALPACA_INTRADAY_API_SECRET")
    if not all(os.getenv(k) for k in required):
        print("BLOCKED: missing credentials")
        return 2
    try:
        import psycopg
        from urllib.parse import quote
        from intraday_engine import api, PAPER
        now=datetime.now(timezone.utc)
        ny=now.astimezone(ZoneInfo("America/New_York"))
        if ny.weekday() >= 5:
            raise ValueError("not_a_weekday")
        from intraday_calendar import verify_clock
        clock=api(PAPER,"/v2/clock")
        calendar=api(PAPER,"/v2/calendar?start="+ny.date().isoformat()+"&end="+ny.date().isoformat())
        if not isinstance(calendar,list) or len(calendar)!=1:
            raise ValueError("market_calendar_unavailable")
        # Verify today's actual exchange session rather than assuming weekdays are trading days.
        if calendar[0].get("date")!=ny.date().isoformat():
            raise ValueError("not_a_trading_session")
        account=api(PAPER,"/v2/account")
        positions=api(PAPER,"/v2/positions")
        open_orders=api(PAPER,"/v2/orders?status=open&limit=500")
        start=ny.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).isoformat()
        history=api(PAPER,"/v2/orders?status=all&limit=500&nested=false&after="+quote(start))
        state=validate(account,positions,open_orders,history,now,
                       isinstance(history,list) and len(history)<500)
        with psycopg.connect(os.environ["INTRADAY_DATABASE_URL"],connect_timeout=8,sslmode="require") as conn:
            insert_session(conn,state)
        print(json.dumps({"status":"initialized_blocked","session_date":state["date"].isoformat(),
                          "trading_blocked":True,"orders_submitted":0,
                          "equity":str(state["equity"]),"prior_close_equity":str(state["prior_close"])}))
        return 0
    except Exception as exc:
        if isinstance(exc, ValueError):
            print("BLOCKED: session initialization refused (" + str(exc) + ")")
        else:
            print("BLOCKED: session initialization failed (" + type(exc).__name__ + ")")
        return 3

if __name__=="__main__":
    sys.exit(main())
