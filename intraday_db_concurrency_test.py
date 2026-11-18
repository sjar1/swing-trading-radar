"""Destructive ONLY to a uniquely named, ephemeral PostgreSQL test schema.

Never touches intraday_paper; never connects to broker APIs; never submits orders.
Requires INTRADAY_DATABASE_URL and an explicit test confirmation in GitHub Actions.
"""
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

DATE=date(2099,1,2)
def run():
    import psycopg
    from psycopg import sql
    url=os.environ["INTRADAY_DATABASE_URL"]
    name="intraday_test_"+uuid.uuid4().hex[:16]
    ident=sql.Identifier(name)
    outcomes=[]
    def note(label, passed):
        outcomes.append({"scenario":label,"passed":bool(passed)})
    def connect():
        return psycopg.connect(url,connect_timeout=8,sslmode="require",autocommit=True)
    def reservation(key, risk=25, fail_after_insert=False):
        with connect() as conn:
            try:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(sql.SQL("SELECT trading_blocked FROM {}.sessions WHERE session_date=%s FOR UPDATE").format(ident),(DATE,))
                        row=cur.fetchone()
                        if row is None or row[0]: return "blocked"
                        cur.execute(sql.SQL("SELECT count(*),coalesce(sum(reserved_risk),0) FROM {}.order_intents WHERE session_date=%s").format(ident),(DATE,))
                        count,used=cur.fetchone()
                        if count>=5 or Decimal(str(used))+Decimal(str(risk))>100: return "limit"
                        cur.execute(sql.SQL("INSERT INTO {}.order_intents(client_order_id,session_date,reserved_risk) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING RETURNING client_order_id").format(ident),(key,DATE,risk))
                        if cur.fetchone() is None: return "duplicate"
                        if fail_after_insert: raise RuntimeError("simulated_crash_before_commit")
                return "reserved"
            except RuntimeError as exc:
                if str(exc)=="simulated_crash_before_commit": return "rolled_back"
                raise
    with connect() as admin:
        try:
            with admin.cursor() as cur:
                cur.execute(sql.SQL("CREATE SCHEMA {}").format(ident))
                cur.execute(sql.SQL("CREATE TABLE {}.sessions(session_date date PRIMARY KEY,trading_blocked boolean NOT NULL)").format(ident))
                cur.execute(sql.SQL("CREATE TABLE {}.order_intents(client_order_id text PRIMARY KEY,session_date date NOT NULL REFERENCES {}.sessions(session_date),reserved_risk numeric NOT NULL CHECK(reserved_risk>0 AND reserved_risk<=25))").format(ident,ident))
                cur.execute(sql.SQL("INSERT INTO {}.sessions VALUES(%s,FALSE)").format(ident),(DATE,))
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(reservation,["intraday-test-duplicate"]*2))
            note("Concurrent duplicate ID",sorted(results)==["duplicate","reserved"])
            with ThreadPoolExecutor(max_workers=6) as pool:
                results=list(pool.map(reservation,["intraday-test-risk-"+str(i) for i in range(6)]))
            # One prior successful reservation consumes $25; only three more may fit.
            note("Concurrent daily risk cap",results.count("reserved")==3 and results.count("limit")==3)
            with admin.cursor() as cur:
                cur.execute(sql.SQL("SELECT count(*),sum(reserved_risk) FROM {}.order_intents").format(ident))
                count,total=cur.fetchone()
            note("Atomic budget invariants",count==4 and total==100)
            note("Simulated crash rolls back",reservation("intraday-test-crash",fail_after_insert=True)=="limit" if count==4 else False)
            # Free one budget slot, inject crash, then confirm no residual intent.
            with admin.cursor() as cur:
                cur.execute(sql.SQL("DELETE FROM {}.order_intents WHERE client_order_id=%s").format(ident),("intraday-test-duplicate",))
            crash=reservation("intraday-test-crash",fail_after_insert=True)
            with admin.cursor() as cur:
                cur.execute(sql.SQL("SELECT count(*) FROM {}.order_intents WHERE client_order_id=%s").format(ident),("intraday-test-crash",))
                residual=cur.fetchone()[0]
            note("Rollback leaves no intent",crash=="rolled_back" and residual==0)
            with admin.cursor() as cur:
                cur.execute(sql.SQL("UPDATE {}.sessions SET trading_blocked=TRUE WHERE session_date=%s").format(ident),(DATE,))
            note("Blocked session refuses reservation",reservation("intraday-test-blocked")=="blocked")
            # A missing broker acknowledgement must never cause automatic resubmission.
            from intraday_crash_recovery import recovery_plan
            ledger={"version":1,"session_date":DATE.isoformat(),"entries":{
                "intraday-test-ambiguous":{"state":"reserved","reserved_risk":25}}}
            recovery=recovery_plan(ledger,DATE.isoformat(),[],[])
            note("Ambiguous broker acknowledgement: no retry",
                 recovery["retry_submission"] is False and recovery["execution_enabled"] is False)
        finally:
            # Drop ONLY the unique schema created by this run.
            with admin.cursor() as cur:
                cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(ident))
    return {"scenarios":outcomes,"passed":sum(x["passed"] for x in outcomes),
            "total":len(outcomes),"orders_submitted":0,"execution_enabled":False,
            "production_schema_modified":False}

def main():
    if os.getenv("INTRADAY_DB_TEST_CONFIRM")!="ISOLATED_TEST_ONLY":
        print("BLOCKED: explicit isolated test confirmation missing")
        return 2
    try:
        result=run()
        print(json.dumps(result,sort_keys=True))
        return 0 if result["passed"]==result["total"] else 3
    except Exception as exc:
        print("BLOCKED: isolated database test failed ("+type(exc).__name__+")")
        return 3
if __name__=="__main__":
    sys.exit(main())
