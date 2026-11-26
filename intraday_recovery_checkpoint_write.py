"""Durable recovery checkpoint CAS adapter for isolated integration tests only.

Writes are prohibited to production intraday_paper schema. This module never
calls Alpaca or enables trading. All writes require an explicit test schema.
"""
import re
from datetime import date
from intraday_recovery_journal import RecoveryJournal,checkpoint

class CheckpointWriteBlocked(RuntimeError):
    pass

TEST_SCHEMA=re.compile(r"^intraday_test_[a-f0-9]{16}$")

def persist_isolated(conn,*,schema,session_date,state,expected_revision):
    if not isinstance(schema,str) or not TEST_SCHEMA.fullmatch(schema):
        raise CheckpointWriteBlocked("production_checkpoint_writes_disabled")
    if not isinstance(session_date,date) or isinstance(session_date,__import__("datetime").datetime):
        raise CheckpointWriteBlocked("invalid_session_date")
    if not isinstance(state,RecoveryJournal) or type(expected_revision)!=int or expected_revision<0:
        raise CheckpointWriteBlocked("invalid_checkpoint_write")
    from psycopg import sql
    payload={"session_date":session_date.isoformat(),"state":checkpoint(state),
             "execution_enabled":False}
    # Existing row must be created by the isolated test harness. This function
    # never creates a session or bootstraps production checkpoint storage.
    query=sql.SQL("""UPDATE {}.recovery_checkpoints
        SET checkpoint=%s::jsonb, revision=revision+1, observed_at=now()
        WHERE session_date=%s AND revision=%s
        RETURNING revision""").format(sql.Identifier(schema))
    import json
    with conn.cursor() as cur:
        cur.execute(query,(json.dumps(payload,sort_keys=True),session_date,expected_revision))
        rows=cur.fetchall()
    if len(rows)!=1:
        raise CheckpointWriteBlocked("stale_or_missing_checkpoint_revision")
    return {"revision":rows[0][0],"execution_enabled":False,"broker_writes":0}
