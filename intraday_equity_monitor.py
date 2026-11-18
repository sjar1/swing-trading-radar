"""PAPER-only durable equity observation; never submits orders or unblocks trading."""
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

LIMIT = Decimal("100")

class EquityMonitorBlocked(ValueError):
    pass

def positive(value):
    if isinstance(value, bool):
        raise EquityMonitorBlocked("invalid_equity")
    try:
        x = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise EquityMonitorBlocked("invalid_equity")
    if not x.is_finite() or x <= 0:
        raise EquityMonitorBlocked("invalid_equity")
    return x

def transition(session, current, broker_prior):
    """Compute monotonic peak and sticky block from a locked session row."""
    if session is None:
        raise EquityMonitorBlocked("session_missing")
    prior, peak, last, old_drawdown, blocked, revision = session
    prior, peak, last, old_drawdown = map(positive_or_zero, (prior, peak, last, old_drawdown))
    current, broker_prior = positive(current), positive(broker_prior)
    if prior <= 0 or peak < max(prior,last) or abs(prior-broker_prior) > Decimal("0.01"):
        raise EquityMonitorBlocked("inconsistent_prior_state")
    if revision is None or revision < 0 or not isinstance(blocked,bool):
        raise EquityMonitorBlocked("invalid_session_state")
    new_peak = max(peak,current)
    drawdown = max(Decimal("0"),new_peak-current,prior-current)
    # Never reset a previously reached loss limit, even after equity recovers.
    new_blocked = blocked or old_drawdown >= LIMIT or drawdown >= LIMIT
    return {"peak":new_peak,"last":current,"drawdown":max(old_drawdown,drawdown),
            "blocked":new_blocked,"revision":revision+1}

def positive_or_zero(value):
    if isinstance(value,bool):
        raise EquityMonitorBlocked("invalid_equity")
    try:
        x=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):
        raise EquityMonitorBlocked("invalid_equity")
    if not x.is_finite() or x < 0:
        raise EquityMonitorBlocked("invalid_equity")
    return x

def record(conn, session_date, sampled_at, equity, broker_prior):
    if sampled_at.tzinfo is None or sampled_at.astimezone(ZoneInfo("America/New_York")).date()!=session_date:
        raise EquityMonitorBlocked("invalid_sample_date")
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT prior_close_equity,peak_equity,last_equity,drawdown,trading_blocked,revision "
                            "FROM intraday_paper.sessions WHERE session_date=%s FOR UPDATE",(session_date,))
                state=transition(cur.fetchone(),equity,broker_prior)
                cur.execute("SELECT max(sampled_at) FROM intraday_paper.equity_samples WHERE session_date=%s",(session_date,))
                latest=cur.fetchone()[0]
                if latest is None or sampled_at<=latest:
                    raise EquityMonitorBlocked("stale_or_duplicate_equity_sample")
                cur.execute("INSERT INTO intraday_paper.equity_samples (session_date,sampled_at,equity) "
                            "VALUES (%s,%s,%s)",(session_date,sampled_at,state["last"]))
                cur.execute("UPDATE intraday_paper.sessions SET peak_equity=%s,last_equity=%s,drawdown=%s,"
                            "trading_blocked=%s,revision=%s,updated_at=now() WHERE session_date=%s",
                            (state["peak"],state["last"],state["drawdown"],state["blocked"],state["revision"],session_date))
        return state
    except EquityMonitorBlocked:
        raise
    except Exception as exc:
        raise EquityMonitorBlocked("database_update_failed") from exc

def main():
    if not all(os.getenv(k) for k in ("INTRADAY_DATABASE_URL","ALPACA_INTRADAY_API_KEY","ALPACA_INTRADAY_API_SECRET")):
        print("BLOCKED: required secrets missing")
        return 2
    try:
        import psycopg
        from intraday_engine import api,PAPER
        # Broker read only; this workflow never calls order submission endpoints.
        account=api(PAPER,"/v2/account")
        if account.get("status")!="ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
            raise EquityMonitorBlocked("broker_account_blocked")
        now=datetime.now(timezone.utc)
        day=now.astimezone(ZoneInfo("America/New_York")).date()
        with psycopg.connect(os.environ["INTRADAY_DATABASE_URL"],connect_timeout=8,sslmode="require") as conn:
            result=record(conn,day,now,account.get("equity"),account.get("last_equity"))
        print(json.dumps({"date":day.isoformat(),"sample_saved":True,"peak_equity":str(result["peak"]),
                          "equity":str(result["last"]),"drawdown":str(result["drawdown"]),
                          "trading_blocked":result["blocked"],"revision":result["revision"],
                          "orders_submitted":0,"execution_enabled":False},sort_keys=True))
        return 0
    except Exception as exc:
        label=str(exc) if isinstance(exc,EquityMonitorBlocked) else type(exc).__name__
        print("BLOCKED: equity monitor refused ("+label+")")
        return 3

if __name__=="__main__":
    sys.exit(main())
