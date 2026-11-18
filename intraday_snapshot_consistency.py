"""Fail-closed identity comparison of two read-only durable session snapshots."""
from intraday_durable_fill_reconciliation import DurableFillBlocked

def verify_snapshots(*,event_rows,intents):
    if not isinstance(event_rows,list) or not isinstance(intents,list):
        raise DurableFillBlocked("invalid_snapshot")
    observed={}
    for row in event_rows:
        if not isinstance(row,(tuple,list)) or len(row)!=8:
            raise DurableFillBlocked("invalid_event_snapshot")
        client,symbol,broker_id=row[:3]
        if client in observed and observed[client]!=(symbol,broker_id):
            raise DurableFillBlocked("conflicting_event_snapshot")
        observed[client]=(symbol,broker_id)
    expected={}
    for row in intents:
        if not isinstance(row,(tuple,list)) or len(row)!=3:
            raise DurableFillBlocked("invalid_intent_snapshot")
        client,symbol,broker_id=row
        if client in expected:
            raise DurableFillBlocked("duplicate_intent_snapshot")
        expected[client]=(symbol,broker_id)
    if observed!=expected:
        raise DurableFillBlocked("durable_snapshot_identity_mismatch")
    return {"status":"durable_snapshot_identities_match",
            "identity_count":len(expected),"restart_clear":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
