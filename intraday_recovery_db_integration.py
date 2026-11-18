"""Isolated Supabase recovery checkpoint transaction integration test.

Creates and drops an ephemeral test schema. Does not access broker endpoints,
production trading tables, or execute orders.
"""
import json,os,sys,uuid
from datetime import date,datetime,timezone,timedelta
from psycopg import sql
import psycopg
from intraday_recovery_journal import RecoveryJournal,advance,checkpoint
from intraday_recovery_checkpoint_write import persist_isolated,CheckpointWriteBlocked
from intraday_recovery_restart_gate import restart_observation,RestartBlocked
from intraday_recovery_checkpoint_db import make_checkpoint

def run():
    if os.getenv("INTRADAY_DB_TEST_CONFIRM")!="ISOLATED_TEST_ONLY":
        raise ValueError("isolated_test_confirmation_missing")
    url=os.environ["INTRADAY_DATABASE_URL"]
    schema="intraday_test_"+uuid.uuid4().hex[:16]
    ident=sql.Identifier(schema)
    results={}
    created=False
    with psycopg.connect(url,connect_timeout=8,sslmode="require",autocommit=True) as conn:
        try:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(ident))
            created=True
            conn.execute(sql.SQL("""CREATE TABLE {}.recovery_checkpoints (
                session_date date PRIMARY KEY, checkpoint jsonb NOT NULL,
                observed_at timestamptz NOT NULL DEFAULT now(),
                revision bigint NOT NULL DEFAULT 0)""").format(ident))
            day=date(2026,11,18)
            conn.execute(sql.SQL("INSERT INTO {}.recovery_checkpoints(session_date,checkpoint) VALUES (%s,%s::jsonb)").format(ident),
                (day,json.dumps(make_checkpoint(day.isoformat(),RecoveryJournal()))))
            state=advance(RecoveryJournal(),{"sequence":1,"snapshot_complete":True,
                "ownership_verified":True,"open_order_ids":["test-order"],"positions":{}})
            first=persist_isolated(conn,schema=schema,session_date=day,state=state,expected_revision=0)
            results["cas_first_revision"]=first["revision"]==1
            try:
                persist_isolated(conn,schema=schema,session_date=day,state=state,expected_revision=0)
                results["stale_revision_rejected"]=False
            except CheckpointWriteBlocked:
                results["stale_revision_rejected"]=True
            row=conn.execute(sql.SQL("SELECT checkpoint,revision FROM {}.recovery_checkpoints WHERE session_date=%s").format(ident),(day,)).fetchone()
            saved=row[0] if isinstance(row[0],dict) else json.loads(row[0])
            results["durable_checkpoint_written"]=row[1]==1 and saved["state"]["last_sequence"]==1
            now=datetime.now(timezone.utc)
            try:
                restart_observation(saved,session_date=day.isoformat(),
                    checkpoint_observed_at=now-timedelta(seconds=5),now=now,
                    broker_observation={"sequence":2,"observed_at":now.isoformat(),
                        "snapshot_complete":False,"ownership_verified":False,
                        "open_order_ids":[],"positions":{}})
                results["unverified_restart_rejected"]=False
            except RestartBlocked:
                results["unverified_restart_rejected"]=True
        finally:
            if created:
                conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(ident))
    results["isolated_schema_dropped"]=True
    print(json.dumps({"checks":results,"all_passed":all(results.values()),
        "broker_writes":0,"execution_enabled":False},sort_keys=True))
    return 0 if all(results.values()) else 3

if __name__=="__main__":
    try:sys.exit(run())
    except Exception as exc:
        print("BLOCKED: isolated recovery integration failed ("+type(exc).__name__+")")
        sys.exit(3)
