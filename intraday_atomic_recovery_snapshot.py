"""One repeatable-read, read-only PostgreSQL snapshot for PAPER recovery evidence.

All three projections come from the same joined rows and database transaction.
No broker writes, no database writes, no trading authorization.
"""
from intraday_durable_fill_reconciliation import DurableFillBlocked

def project(rows):
    if not isinstance(rows,list):
        raise DurableFillBlocked("invalid_atomic_snapshot")
    intents={}
    states={}
    event_rows=[]
    event_ids=set()
    execution_rows=[]
    for row in rows:
        if not isinstance(row,(tuple,list)) or len(row)!=9:
            raise DurableFillBlocked("invalid_atomic_snapshot_row")
        client,symbol,broker_id,state,event_id,event_broker,status,event_at,payload=row
        if not isinstance(client,str) or not client.startswith("intraday-") or not isinstance(symbol,str) or not symbol:
            raise DurableFillBlocked("invalid_atomic_snapshot_identity")
        if broker_id is not None and (not isinstance(broker_id,str) or not broker_id):
            raise DurableFillBlocked("invalid_atomic_snapshot_broker_id")
        if not isinstance(state,str) or not state:
            raise DurableFillBlocked("invalid_atomic_snapshot_state")
        if event_id is None and any(x is not None for x in (event_broker,status,event_at,payload)):
            raise DurableFillBlocked("partial_atomic_snapshot_event")
        identity=(symbol,broker_id)
        if client in intents and intents[client]!=identity:
            raise DurableFillBlocked("atomic_snapshot_identity_conflict")
        if client in states and states[client]!=state:
            raise DurableFillBlocked("atomic_snapshot_state_conflict")
        intents[client]=identity
        states[client]=state
        if event_id is not None:
            if type(event_id) is not int or event_id<=0 or event_id in event_ids:
                raise DurableFillBlocked("duplicate_or_invalid_atomic_event_id")
            event_ids.add(event_id)
        event_rows.append((client,symbol,broker_id,state,event_id,event_broker,status,event_at))
        execution_rows.append((client,symbol,broker_id,event_id,status,payload,event_broker))
    return {"intents":[(client,*identity) for client,identity in intents.items()],
            "event_rows":event_rows,"execution_rows":execution_rows,
            "snapshot_atomic":False,"broker_writes":0,"execution_enabled":False}

def load_atomic_snapshot(db_url,session_date,max_rows=2000):
    if not isinstance(db_url,str) or not db_url or not isinstance(session_date,str) or not session_date or type(max_rows) is not int or not 1<=max_rows<=10000:
        raise DurableFillBlocked("invalid_atomic_snapshot_parameters")
    import psycopg
    with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("""SELECT i.client_order_id,i.symbol,i.broker_order_id,i.state,
                                  e.id,e.broker_order_id,e.broker_status,e.event_at,e.payload
                           FROM intraday_paper.order_intents i
                           LEFT JOIN intraday_paper.order_events e ON e.client_order_id=i.client_order_id
                           WHERE i.session_date=%s ORDER BY i.client_order_id,e.event_at,e.id
                           LIMIT %s""",(session_date,max_rows+1))
            rows=cur.fetchall()
            if len(rows)>max_rows:
                raise DurableFillBlocked("atomic_snapshot_row_limit_exceeded")
            result=project(rows)
            result["snapshot_atomic"]=True
            return result
