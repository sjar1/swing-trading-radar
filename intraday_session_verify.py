"""Independent read-only verification of durable blocked PAPER session."""
import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

def verify(session, samples, intents):
    problems=[]
    if session is None:
        return {"verified":False,"problems":["session_missing"]}
    prior, peak, last, drawdown, blocked, revision = session
    if blocked is not True: problems.append("session_not_blocked")
    if any(x is None or not Decimal(str(x)).is_finite() for x in (prior,peak,last,drawdown)):
        problems.append("invalid_equity")
    else:
        if min(prior,peak,last)<=0 or drawdown<0 or peak<last or peak<prior:
            problems.append("inconsistent_equity")
    if revision is None or revision<0: problems.append("invalid_revision")
    if not samples: problems.append("equity_sample_missing")
    else:
        if any(Decimal(str(x[1]))<=0 for x in samples):
            problems.append("invalid_sample")
        if Decimal(str(samples[0][1])) != Decimal(str(last)):
            problems.append("sample_equity_mismatch")
    if intents: problems.append("unexpected_order_intents")
    return {"verified":not problems,"problems":problems,"sample_count":len(samples),
            "intent_count":len(intents),"trading_blocked":blocked,"execution_enabled":False}

def main():
    if not os.getenv("INTRADAY_DATABASE_URL"):
        print("BLOCKED: database secret missing")
        return 2
    try:
        import psycopg
        today=datetime.now(ZoneInfo("America/New_York")).date()
        with psycopg.connect(os.environ["INTRADAY_DATABASE_URL"],connect_timeout=8,sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT prior_close_equity,peak_equity,last_equity,drawdown,trading_blocked,revision "
                            "FROM intraday_paper.sessions WHERE session_date=%s",(today,))
                session=cur.fetchone()
                cur.execute("SELECT sampled_at,equity FROM intraday_paper.equity_samples "
                            "WHERE session_date=%s ORDER BY sampled_at DESC",(today,))
                samples=cur.fetchall()
                cur.execute("SELECT client_order_id FROM intraday_paper.order_intents WHERE session_date=%s",(today,))
                intents=cur.fetchall()
        result=verify(session,samples,intents)
        print(json.dumps({"date":today.isoformat(),**result},sort_keys=True))
        return 0 if result["verified"] else 3
    except Exception as exc:
        print("BLOCKED: verification failed ("+type(exc).__name__+")")
        return 3

if __name__=="__main__":
    sys.exit(main())
