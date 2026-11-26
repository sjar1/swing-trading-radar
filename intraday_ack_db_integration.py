"""Isolated Supabase transaction test for the actual durable acknowledgement adapter.

Creates and drops a unique synthetic schema. No Alpaca credentials or broker calls.
"""
import json,os,sys,uuid
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import psycopg
from psycopg import sql
from intraday_durable_ack import transition,TransitionBlocked

def run():
    if os.getenv("INTRADAY_DB_TEST_CONFIRM")!="ISOLATED_TEST_ONLY":
        raise ValueError("isolated_test_confirmation_missing")
    url=os.environ["INTRADAY_DATABASE_URL"]
    schema="intraday_test_"+uuid.uuid4().hex[:16]
    ident=sql.Identifier(schema)
    created=False
    results={}
    def connect():
        return psycopg.connect(url,connect_timeout=8,sslmode="require",autocommit=True)
    with connect() as conn:
        try:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(ident))
            created=True
            conn.execute(sql.SQL("CREATE TABLE {}.order_intents (client_order_id text PRIMARY KEY, state text NOT NULL, broker_order_id text, updated_at timestamptz NOT NULL DEFAULT now())").format(ident))
            conn.execute(sql.SQL("CREATE TABLE {}.order_events (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,client_order_id text NOT NULL,broker_order_id text,broker_status text NOT NULL,event_at timestamptz NOT NULL,payload jsonb NOT NULL, UNIQUE(client_order_id,broker_order_id,broker_status,event_at))").format(ident))
            conn.execute(sql.SQL("INSERT INTO {}.order_intents (client_order_id,state) VALUES ('intraday-test-ack','reserved')").format(ident))
            def change(state,broker=None,status=None):
                with connect() as other:
                    return transition(other,"intraday-test-ack",state,broker,status,schema=schema)
            results["mark_unknown"]=change("unknown")["state"]=="unknown"
            def compete():
                try:return change("accepted","broker-test-1","accepted")["state"]
                except TransitionBlocked:return "blocked"
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(compete) for _ in range(2)]
                outcomes=[x.result() for x in futures]
            results["concurrent_ack_once"]=sorted(outcomes)==["accepted","blocked"]
            try:change("filled","broker-wrong","filled");results["mismatch_rejected"]=False
            except TransitionBlocked:results["mismatch_rejected"]=True
            results["filled"]=change("filled","broker-test-1","filled")["state"]=="filled"
            try:change("accepted","broker-test-1","accepted");results["regression_rejected"]=False
            except TransitionBlocked:results["regression_rejected"]=True
            rows=conn.execute(sql.SQL("SELECT state,broker_order_id FROM {}.order_intents").format(ident)).fetchall()
            events=conn.execute(sql.SQL("SELECT broker_status FROM {}.order_events").format(ident)).fetchall()
            results["durable_final_state"]=rows==[("filled","broker-test-1")]
            results["events_persisted"]=sorted(x[0] for x in events)==["accepted","filled"]
        finally:
            if created:
                conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(ident))
    print(json.dumps({"isolated_schema_dropped":True,"checks":results,"all_passed":all(results.values()),"broker_writes":0},sort_keys=True))
    return 0 if all(results.values()) else 3

if __name__=="__main__":
    try:sys.exit(run())
    except Exception as exc:
        print("BLOCKED: isolated acknowledgement integration failed ("+type(exc).__name__+")")
        sys.exit(3)
