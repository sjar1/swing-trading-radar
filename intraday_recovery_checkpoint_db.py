"""Recovery checkpoint database adapter; never touches Alpaca or authorizes execution.

Requires explicit isolated test schema for writes; production is read-only.
"""
import json
from intraday_recovery_journal import checkpoint,restore,RecoveryJournalBlocked

class CheckpointBlocked(RuntimeError):
    pass

def validate_checkpoint(payload, *, session_date, max_age_seconds, observed_at, now):
    from datetime import datetime,timezone
    if not isinstance(payload,dict) or payload.get("session_date")!=session_date:
        raise CheckpointBlocked("session_mismatch")
    if not isinstance(max_age_seconds,int) or isinstance(max_age_seconds,bool) or not 1<=max_age_seconds<=300:
        raise CheckpointBlocked("invalid_freshness_limit")
    if not isinstance(now,datetime) or now.tzinfo is None or not isinstance(observed_at,datetime) or observed_at.tzinfo is None:
        raise CheckpointBlocked("invalid_observation_time")
    age=(now.astimezone(timezone.utc)-observed_at.astimezone(timezone.utc)).total_seconds()
    if age<0 or age>max_age_seconds:
        raise CheckpointBlocked("stale_checkpoint")
    try:
        state=restore(payload["state"])
    except (KeyError,RecoveryJournalBlocked,TypeError):
        raise CheckpointBlocked("invalid_checkpoint")
    return {"state":state,"fresh":True,"entry_permitted":False,"execution_enabled":False,"broker_writes":0}

def read_checkpoint(conn,session_date):
    from datetime import date
    if not isinstance(session_date,date):
        raise CheckpointBlocked("invalid_session_date")
    with conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SELECT checkpoint,observed_at FROM intraday_paper.recovery_checkpoints WHERE session_date=%s",(session_date,))
        rows=cur.fetchall()
    if len(rows)>1:raise CheckpointBlocked("duplicate_checkpoint")
    return rows[0] if rows else None

def make_checkpoint(session_date,state):
    if not isinstance(session_date,str) or not session_date:
        raise CheckpointBlocked("invalid_session_date")
    return {"session_date":session_date,"state":checkpoint(state),"execution_enabled":False}
