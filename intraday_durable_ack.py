"""Durable fail-closed broker acknowledgement transitions for PAPER order intents.

No Alpaca network writes. All transitions use transactional row locks and
explicit broker evidence. Never retries an uncertain submission.
"""
from datetime import datetime,timezone

class TransitionBlocked(RuntimeError):
    pass

ALLOWED={
    "reserved":{"unknown"},
    "unknown":{"submitted","accepted","partially_filled","filled","canceled","rejected","expired"},
    "submitted":{"accepted","partially_filled","filled","canceled","rejected","expired","unknown"},
    "accepted":{"partially_filled","filled","canceled","rejected","expired","unknown"},
    "partially_filled":{"filled","canceled","expired","unknown"},
    "filled":{"closed"},
    "canceled":set(),"rejected":set(),"expired":set(),"closed":set(),
}

def transition(conn,client_order_id,new_state,broker_order_id=None,broker_status=None,event_at=None):
    if not isinstance(client_order_id,str) or not client_order_id.startswith("intraday-"):
        raise TransitionBlocked("invalid_client_id")
    if new_state not in {x for values in ALLOWED.values() for x in values}:
        raise TransitionBlocked("invalid_target_state")
    if new_state not in ("unknown",) and (not broker_order_id or not broker_status):
        raise TransitionBlocked("broker_evidence_required")
    if event_at is not None and (not isinstance(event_at,datetime) or event_at.tzinfo is None):
        raise TransitionBlocked("invalid_event_timestamp")
    event_at=event_at or datetime.now(timezone.utc)
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT state,broker_order_id FROM intraday_paper.order_intents WHERE client_order_id=%s FOR UPDATE",(client_order_id,))
                row=cur.fetchone()
                if row is None: raise TransitionBlocked("intent_missing")
                old,existing_id=row
                if new_state not in ALLOWED.get(old,set()):
                    raise TransitionBlocked("illegal_or_duplicate_transition")
                if existing_id and broker_order_id and existing_id!=broker_order_id:
                    raise TransitionBlocked("broker_id_mismatch")
                if old=="reserved" and new_state!="unknown":
                    raise TransitionBlocked("must_mark_ambiguous_before_network")
                cur.execute("UPDATE intraday_paper.order_intents SET state=%s,broker_order_id=coalesce(broker_order_id,%s),updated_at=now() WHERE client_order_id=%s",
                            (new_state,broker_order_id,client_order_id))
                if broker_order_id:
                    cur.execute("INSERT INTO intraday_paper.order_events (client_order_id,broker_order_id,broker_status,event_at,payload) VALUES (%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                                (client_order_id,broker_order_id,broker_status,event_at,"{}"))
        return {"client_order_id":client_order_id,"state":new_state,"retry_submission":False,"execution_enabled":False}
    except TransitionBlocked:
        raise
    except Exception as exc:
        raise TransitionBlocked("database_transition_failed") from exc

def next_action(state,broker_order_id):
    if state=="reserved":
        return "mark_unknown_before_any_submission"
    if state=="unknown":
        return "manual_broker_reconciliation_no_retry"
    if state in ("submitted","accepted","partially_filled"):
        return "observe_broker_only"
    if state in ("filled","canceled","rejected","expired","closed"):
        return "do_not_resubmit"
    raise TransitionBlocked("unknown_state")
