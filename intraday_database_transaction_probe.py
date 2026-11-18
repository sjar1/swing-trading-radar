"""Manual, isolated PostgreSQL transaction probe. No Alpaca network calls.

Uses an existing blocked intraday session and a transaction that is ALWAYS
rolled back. No committed writes, no order submission, no permission changes.
"""
import json,os,sys
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4

def inspect(db_url,session_date):
    if not isinstance(db_url,str) or not db_url:
        raise ValueError("database_url_required")
    import psycopg
    # A read-only transaction checks that the schema and session are present.
    with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("""SELECT trading_blocked FROM intraday_paper.sessions
                           WHERE session_date=%s""",(session_date,))
            session=cur.fetchone()
            if session is None:
                return {"status":"blocked_session_missing","database_writes_committed":0,
                        "broker_writes":0,"entry_permitted":False,"execution_enabled":False}
            if session[0] is not True:
                raise ValueError("session_must_be_blocked")
    client="intraday-db-probe-"+uuid4().hex
    # Deliberately rollback even if every statement succeeds.
    with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""SELECT trading_blocked FROM intraday_paper.sessions
                               WHERE session_date=%s FOR UPDATE""",(session_date,))
                row=cur.fetchone()
                if row is None or row[0] is not True:
                    raise ValueError("session_not_blocked")
                cur.execute("""INSERT INTO intraday_paper.order_intents
                               (client_order_id,session_date,symbol,strategy,reserved_risk,state)
                               VALUES (%s,%s,'AMD','opening_range_breakout',1,'reserved')""",
                            (client,session_date))
                cur.execute("""SELECT state FROM intraday_paper.order_intents
                               WHERE client_order_id=%s""",(client,))
                if cur.fetchone()!=("reserved",):
                    raise ValueError("transaction_readback_failed")
        finally:
            conn.rollback()
    # Verify the rollback from an independent connection.
    with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT COUNT(*) FROM intraday_paper.order_intents WHERE client_order_id=%s",(client,))
            if cur.fetchone()!=(0,):
                raise ValueError("rollback_not_verified")
    return {"status":"isolated_transaction_rollback_verified",
            "database_writes_committed":0,"broker_writes":0,
            "entry_permitted":False,"execution_enabled":False,
            "restart_clear":False,"manual_approval_required":True}

def main():
    output={"status":"blocked","database_writes_committed":0,"broker_writes":0,
            "entry_permitted":False,"execution_enabled":False}
    try:
        session=datetime.now(ZoneInfo("America/New_York")).date()
        output=inspect(os.getenv("INTRADAY_DATABASE_URL"),session)
        print(json.dumps(output,sort_keys=True))
        return 0 if output["status"]=="isolated_transaction_rollback_verified" else 2
    except Exception as exc:
        output["reason"]=type(exc).__name__
        print(json.dumps(output,sort_keys=True))
        return 3
if __name__=="__main__":sys.exit(main())
