"""Offline SQLite crash/restart test harness. Never connects to Alpaca or production DB."""
import json,sqlite3
from intraday_order_state_replay import replay,ReplayBlocked

class PersistenceBlocked(RuntimeError):pass

def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS simulated_events (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL UNIQUE,
        client_order_id TEXT NOT NULL,
        payload TEXT NOT NULL)""")
    conn.commit()

def persist_event(conn,event):
    if not isinstance(event,dict) or not isinstance(event.get("event_id"),str) or not event["event_id"] or not isinstance(event.get("client_order_id"),str):
        raise PersistenceBlocked("invalid_event")
    try:
        with conn:
            conn.execute("INSERT INTO simulated_events(event_id,client_order_id,payload) VALUES(?,?,?)",
                (event["event_id"],event["client_order_id"],json.dumps(event,sort_keys=True)))
    except (sqlite3.IntegrityError,TypeError,ValueError) as exc:
        raise PersistenceBlocked("duplicate_or_invalid_event") from exc

def recover(conn,client_order_id,broker_order=None):
    rows=conn.execute("SELECT payload FROM simulated_events WHERE client_order_id=? ORDER BY sequence",
                      (client_order_id,)).fetchall()
    events=[]
    for (raw,) in rows:
        try:event=json.loads(raw)
        except (TypeError,ValueError) as exc:raise PersistenceBlocked("corrupt_persisted_event") from exc
        events.append(event)
    state=replay(client_order_id=client_order_id,events=events)
    if broker_order is not None:
        if not isinstance(broker_order,dict) or broker_order.get("client_order_id")!=client_order_id:
            raise PersistenceBlocked("broker_identity_mismatch")
        acknowledged=[e["broker_order_id"] for e in events if e.get("type")=="acknowledged"]
        if not acknowledged or broker_order.get("id")!=acknowledged[-1]:
            raise PersistenceBlocked("broker_acknowledgement_mismatch")
        if broker_order.get("status") not in ("new","accepted","partially_filled","filled","canceled"):
            raise PersistenceBlocked("unknown_broker_status")
        state["broker_order_observed"]=True
    else:
        state["broker_order_observed"]=False
    state["restart_clear"]=False
    state["entry_permitted"]=False
    state["execution_enabled"]=False
    state["broker_writes"]=0
    return state
