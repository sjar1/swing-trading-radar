"""Persist an observed PAPER broker acknowledgment, never submit or retry orders.

A database commit failure is ambiguous; reconcile by client ID before any action.
"""
from datetime import datetime,timezone
from intraday_durable_fill_reconciliation import DurableFillBlocked

ALLOWED={"new","accepted","pending_new","partially_filled","filled","canceled","rejected","expired"}

def validate(*,client_order_id,broker_order,account_verified,broker_base):
    if account_verified is not True or broker_base!="https://paper-api.alpaca.markets":
        raise DurableFillBlocked("paper_identity_not_verified")
    if not isinstance(client_order_id,str) or not client_order_id.startswith("intraday-"):
        raise DurableFillBlocked("invalid_client_order_id")
    if not isinstance(broker_order,dict) or broker_order.get("client_order_id")!=client_order_id:
        raise DurableFillBlocked("broker_ack_identity_mismatch")
    order_id=broker_order.get("id")
    status=broker_order.get("status")
    if not isinstance(order_id,str) or not order_id or status not in ALLOWED:
        raise DurableFillBlocked("broker_ack_incomplete")
    if broker_order.get("side")!="buy" or broker_order.get("asset_class") not in (None,"us_equity"):
        raise DurableFillBlocked("broker_ack_unexpected_order")
    return order_id,status

def persist(*,db_url,client_order_id,broker_order,account_verified,broker_base,observed_at=None):
    broker_id,status=validate(client_order_id=client_order_id,broker_order=broker_order,
                              account_verified=account_verified,broker_base=broker_base)
    if not isinstance(db_url,str) or not db_url:
        raise DurableFillBlocked("database_url_missing")
    if observed_at is None:observed_at=datetime.now(timezone.utc)
    if not isinstance(observed_at,datetime) or observed_at.tzinfo is None:
        raise DurableFillBlocked("invalid_observation_time")
    import psycopg
    try:
        with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT broker_order_id,state FROM intraday_paper.order_intents
                               WHERE client_order_id=%s FOR UPDATE""",(client_order_id,))
                row=cur.fetchone()
                if row is None or row[0] not in (None,broker_id) or row[1] not in ("reserved","submitted","accepted","partially_filled","filled","canceled","rejected","expired"):
                    raise DurableFillBlocked("durable_intent_missing_or_conflicting")
                cur.execute("""SELECT broker_order_id,broker_status FROM intraday_paper.order_events
                               WHERE client_order_id=%s FOR UPDATE""",(client_order_id,))
                prior_events=cur.fetchall()
                if any(e[0]!=broker_id for e in prior_events):
                    raise DurableFillBlocked("conflicting_persisted_broker_identity")
                if any(e[1] in ("filled","canceled","rejected","expired") for e in prior_events):
                    raise DurableFillBlocked("terminal_order_requires_separate_reconciliation")
                cur.execute("""UPDATE intraday_paper.order_intents
                               SET broker_order_id=%s,updated_at=now()
                               WHERE client_order_id=%s""",(broker_id,client_order_id))
                cur.execute("""INSERT INTO intraday_paper.order_events
                               (client_order_id,broker_order_id,broker_status,event_at,payload)
                               VALUES (%s,%s,%s,%s,%s::jsonb)
                               ON CONFLICT (client_order_id,broker_order_id,broker_status,event_at) DO NOTHING""",
                            (client_order_id,broker_id,status,observed_at,"{}"))
        return {"status":"broker_acknowledgement_recorded",
                "retry_submission":False,"restart_clear":False,
                "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
    except DurableFillBlocked:
        raise
    except Exception as exc:
        raise DurableFillBlocked("acknowledgement_commit_unknown_reconcile_before_retry") from exc
