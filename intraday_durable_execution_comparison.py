"""Read-only comparison of explicit durable fill events with Alpaca PAPER orders.

The current order_events schema stores arbitrary JSON payloads; broker_status alone
is NOT fill evidence. Only explicitly identified, unique execution increments count.
This is a bounded diagnostic, never lifetime history certification.
"""
from decimal import Decimal
from urllib.parse import quote
from intraday_broker_fill_quantity import quantity
from intraday_durable_fill_reconciliation import DurableFillBlocked
from intraday_broker_recovery import decide,RecoveryBlocked

def compare_rows(*,rows,api_fn,base,max_orders=20):
    if not isinstance(rows,list) or not callable(api_fn) or type(max_orders) is not int or not 1<=max_orders<=100:
        raise DurableFillBlocked("invalid_fill_event_snapshot")
    if len(rows)>max_orders*100:
        raise DurableFillBlocked("excessive_fill_event_rows")
    ledger={}
    event_ids=set()
    execution_ids=set()
    for row in rows:
        if not isinstance(row,(tuple,list)) or len(row)!=7:
            raise DurableFillBlocked("invalid_fill_event_row")
        client,symbol,broker_id,event_id,status,payload,event_broker_id=row
        if not isinstance(client,str) or not client.startswith("intraday-") or not isinstance(symbol,str) or not symbol:
            raise DurableFillBlocked("invalid_fill_event_identity")
        if broker_id is not None and (not isinstance(broker_id,str) or not broker_id):
            raise DurableFillBlocked("invalid_fill_event_identity")
        if client in ledger and ledger[client]["identity"]!=(symbol,broker_id):
            raise DurableFillBlocked("conflicting_fill_event_identity")
        item=ledger.setdefault(client,{"identity":(symbol,broker_id),"quantity":Decimal(0),"count":0,"incomplete":False})
        if event_id is None:
            if status is not None or payload is not None or event_broker_id is not None:
                raise DurableFillBlocked("partial_fill_event_row")
            continue
        if type(event_id) is not int or event_id<=0 or event_id in event_ids or not isinstance(payload,dict):
            raise DurableFillBlocked("invalid_or_duplicate_fill_event")
        event_ids.add(event_id)
        if event_broker_id is not None and event_broker_id!=broker_id:
            raise DurableFillBlocked("fill_event_broker_identity_mismatch")
        # Only an explicitly tagged execution increment is countable. A status
        # transition, order snapshot, or cumulative filled_qty is not an increment.
        if payload.get("event_type")!="fill":
            if status in ("partially_filled","filled") or "filled_qty" in payload or "fill_qty" in payload:
                item["incomplete"]=True
            continue
        execution_id=payload.get("execution_id")
        if not isinstance(execution_id,str) or not execution_id:
            raise DurableFillBlocked("fill_execution_id_missing")
        if event_broker_id is None or broker_id is None:
            raise DurableFillBlocked("fill_without_durable_broker_identity")
        qty=quantity(payload.get("fill_qty"))
        if qty<=0:
            raise DurableFillBlocked("invalid_execution_increment")
        if execution_id in execution_ids:
            raise DurableFillBlocked("duplicate_execution_id")
        execution_ids.add(execution_id)
        item["quantity"]+=qty
        item["count"]+=1
    if len(ledger)>max_orders:
        raise DurableFillBlocked("excessive_fill_event_intents")
    matched=0
    incomplete=0
    compared=0
    for client,item in ledger.items():
        symbol,broker_id=item["identity"]
        if broker_id is None:
            incomplete+=1
            continue
        try:
            order=api_fn(base,"/v2/orders:by_client_order_id?client_order_id="+quote(client,safe=""))
        except Exception:
            incomplete+=1
            continue
        result=decide(client,"unknown",order)
        if not result["reconciled"]:
            incomplete+=1
            continue
        if result["broker_order_id"]!=broker_id or order.get("symbol")!=symbol:
            raise RecoveryBlocked("fill_event_broker_identity_mismatch")
        matched+=1
        broker_qty=quantity(order.get("filled_qty"))
        if item["incomplete"] or item["count"]==0:
            incomplete+=1
            continue
        if broker_qty!=item["quantity"]:
            raise DurableFillBlocked("broker_durable_execution_quantity_mismatch")
        if item["count"]>0:
            compared+=1
    return {"status":"bounded_explicit_fill_event_comparison",
            "durable_intent_count":len(ledger),"matched_broker_orders":matched,
            "compared_order_count":compared,"incomplete_order_count":incomplete,
            "explicit_execution_count":sum(x["count"] for x in ledger.values()),
            "persisted_event_count":len(event_ids),
            "historical_execution_coverage_proven":False,
            "persisted_fill_quantity_compared":compared>0,
            "snapshot_atomic":False,"historical_event_completeness_verified":False,
            "fill_history_certified":False,"account_history_complete":False,
            "restart_clear":False,"entry_permitted":False,
            "execution_enabled":False,"broker_writes":0}

def load_rows(db_url,session_date):
    if not isinstance(db_url,str) or not db_url or not isinstance(session_date,str) or not session_date:
        raise DurableFillBlocked("invalid_fill_event_query")
    import psycopg
    with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("""SELECT i.client_order_id,i.symbol,i.broker_order_id,
                                  e.id,e.broker_status,e.payload,e.broker_order_id
                           FROM intraday_paper.order_intents i
                           LEFT JOIN intraday_paper.order_events e ON e.client_order_id=i.client_order_id
                           WHERE i.session_date=%s ORDER BY i.client_order_id,e.event_at,e.id""",(session_date,))
            return cur.fetchall()
