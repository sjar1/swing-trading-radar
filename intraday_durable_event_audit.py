"""Read-only audit of persisted intraday order events.

Database event records are observations, not proof of an exhaustive broker history.
Never infers safe restart or execution authorization from a clean event audit.
"""
from datetime import datetime
from intraday_durable_fill_reconciliation import DurableFillBlocked

ALLOWED_STATES=frozenset(("reserved","submitted","accepted","partially_filled",
                          "filled","canceled","rejected","expired","closed","unknown"))

def load_order_event_rows(db_url,session_date):
    if not isinstance(db_url,str) or not db_url.strip() or not isinstance(session_date,str) or not session_date:
        raise DurableFillBlocked("invalid_event_query")
    import psycopg
    with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("""SELECT i.client_order_id,i.symbol,i.broker_order_id,i.state,
                                  e.id,e.broker_order_id,e.broker_status,e.event_at
                           FROM intraday_paper.order_intents i
                           LEFT JOIN intraday_paper.order_events e
                             ON e.client_order_id=i.client_order_id
                           WHERE i.session_date=%s
                           ORDER BY i.client_order_id,e.event_at,e.id""",(session_date,))
            return cur.fetchall()

def audit_rows(rows):
    if not isinstance(rows,list):
        raise DurableFillBlocked("invalid_event_rows")
    intents={}
    events=set()
    total=0
    missing_events=0
    ambiguous=0
    for row in rows:
        if not isinstance(row,(tuple,list)) or len(row)!=8:
            raise DurableFillBlocked("invalid_event_row")
        client,symbol,broker_id,state,event_id,event_broker,status,event_at=row
        if not isinstance(client,str) or not client.startswith("intraday-") or not isinstance(symbol,str) or not symbol or state not in ALLOWED_STATES:
            raise DurableFillBlocked("invalid_durable_order_identity")
        if broker_id is not None and (not isinstance(broker_id,str) or not broker_id):
            raise DurableFillBlocked("invalid_durable_broker_id")
        identity=(symbol,broker_id,state)
        if client in intents and intents[client]!=identity:
            raise DurableFillBlocked("inconsistent_durable_order")
        intents[client]=identity
        if event_id is None:
            if event_broker is not None or status is not None or event_at is not None:
                raise DurableFillBlocked("partial_event_row")
            missing_events+=1
            continue
        if type(event_id) is not int or event_id<=0 or event_id in events:
            raise DurableFillBlocked("invalid_or_duplicate_event_id")
        events.add(event_id)
        if not isinstance(status,str) or not status or not isinstance(event_at,datetime) or event_at.tzinfo is None:
            raise DurableFillBlocked("invalid_event_record")
        if event_broker is not None and (not isinstance(event_broker,str) or not event_broker):
            raise DurableFillBlocked("invalid_event_broker_id")
        if event_broker is not None and broker_id is not None and event_broker!=broker_id:
            raise DurableFillBlocked("event_broker_identity_mismatch")
        total+=1
    for symbol,broker_id,state in intents.values():
        if state in ("submitted","unknown","partially_filled") or (state not in ("reserved","rejected") and broker_id is None):
            ambiguous+=1
    return {"status":"durable_events_audited","intent_count":len(intents),
            "event_count":total,"orders_without_events":missing_events,
            "ambiguous_order_count":ambiguous,
            "durable_event_consistency_verified":True,
            "broker_history_exhaustive":False,"restart_clear":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
