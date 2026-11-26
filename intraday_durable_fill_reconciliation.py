"""Read-only durable intent versus PAPER fill reconciliation.

A session-level consistency check only. Does not certify complete historical
ownership, flattening, or readiness to trade.
"""
from collections import Counter

class DurableFillBlocked(RuntimeError):
    pass

def reconcile_session(intents, fills):
    if not isinstance(intents,list) or not isinstance(fills,list):
        raise DurableFillBlocked("invalid_snapshot")
    ledger={}
    for row in intents:
        if not isinstance(row,(tuple,list)) or len(row)!=3:
            raise DurableFillBlocked("invalid_durable_intent")
        client,symbol,broker_id=row
        if not isinstance(client,str) or not client.startswith("intraday-") or not isinstance(symbol,str) or not symbol or (broker_id is not None and not isinstance(broker_id,str)):
            raise DurableFillBlocked("invalid_durable_intent")
        if client in ledger:
            raise DurableFillBlocked("duplicate_durable_intent")
        ledger[client]=(symbol,broker_id)
    seen=set()
    counts=Counter()
    for fill in fills:
        if not isinstance(fill,dict) or not isinstance(fill.get("event_id"),str) or not fill["event_id"]:
            raise DurableFillBlocked("invalid_fill")
        if fill["event_id"] in seen:
            raise DurableFillBlocked("duplicate_fill")
        seen.add(fill["event_id"])
        client=fill.get("client_order_id")
        order_id=fill.get("order_id")
        if client not in ledger:
            raise DurableFillBlocked("fill_without_durable_intent")
        symbol,stored_broker_id=ledger[client]
        if fill.get("symbol")!=symbol or not isinstance(order_id,str) or not order_id:
            raise DurableFillBlocked("fill_identity_mismatch")
        if stored_broker_id is None or stored_broker_id!=order_id:
            raise DurableFillBlocked("fill_broker_id_not_durably_acknowledged")
        counts[client]+=1
    return {"session_intent_count":len(ledger),"matched_fill_count":sum(counts.values()),
            "intents_with_fills":len(counts),"session_consistency_verified":True,
            "account_history_complete":False,"position_attribution_certified":False,
            "execution_enabled":False,"broker_writes":0}

def load_session_intents(db_url,session_date):
    if not isinstance(db_url,str) or not db_url or not isinstance(session_date,str) or not session_date:
        raise DurableFillBlocked("invalid_database_parameters")
    import psycopg
    with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT client_order_id,symbol,broker_order_id FROM intraday_paper.order_intents WHERE session_date=%s",(session_date,))
            return cur.fetchall()
