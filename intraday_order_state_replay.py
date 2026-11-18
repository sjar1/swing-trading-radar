"""Fail-closed replay of durable order events; never authorizes broker writes."""
from decimal import Decimal,InvalidOperation

class ReplayBlocked(RuntimeError):pass

ALLOWED={
 "reserved":{"submission_attempted"},
 "submission_unknown":{"acknowledged","submission_timeout"},
 "needs_reconciliation":{"acknowledged","canceled","rejected"},
 "acknowledged":{"partially_filled","filled","canceled","rejected"},
 "partially_filled":{"partially_filled","filled","canceled"},
 "filled":set(),"canceled":set(),"rejected":set(),
}
PHASE={"submission_attempted":"submission_unknown","submission_timeout":"needs_reconciliation",
       "acknowledged":"acknowledged","partially_filled":"partially_filled",
       "filled":"filled","canceled":"canceled","rejected":"rejected"}

def replay(*,client_order_id,events):
    if not isinstance(client_order_id,str) or not client_order_id.startswith("intraday-") or not isinstance(events,list):
        raise ReplayBlocked("invalid_replay_input")
    phase="reserved"
    broker_id=None
    filled=Decimal(0)
    seen=set()
    for event in events:
        if not isinstance(event,dict) or not isinstance(event.get("event_id"),str) or not event["event_id"] or event["event_id"] in seen:
            raise ReplayBlocked("invalid_or_duplicate_event")
        seen.add(event["event_id"])
        if event.get("client_order_id")!=client_order_id:
            raise ReplayBlocked("order_identity_mismatch")
        kind=event.get("type")
        if kind not in ALLOWED[phase]:
            raise ReplayBlocked("invalid_order_transition")
        if kind=="acknowledged":
            candidate=event.get("broker_order_id")
            if not isinstance(candidate,str) or not candidate:
                raise ReplayBlocked("missing_broker_acknowledgement")
            if broker_id is not None and broker_id!=candidate:
                raise ReplayBlocked("broker_identity_changed")
            broker_id=candidate
        if kind in ("partially_filled","filled"):
            if broker_id is None or event.get("broker_order_id")!=broker_id:
                raise ReplayBlocked("fill_without_broker_identity")
            try:qty=Decimal(str(event.get("fill_qty")))
            except (InvalidOperation,ValueError,TypeError):
                raise ReplayBlocked("invalid_fill_quantity") from None
            if not qty.is_finite() or qty<=0:
                raise ReplayBlocked("invalid_fill_quantity")
            filled+=qty
        phase=PHASE[kind]
    unresolved=phase in ("submission_unknown","needs_reconciliation","acknowledged","partially_filled")
    return {"status":"replayed_observation_only","phase":phase,
            "filled_quantity":str(filled),"event_count":len(seen),
            "requires_broker_reconciliation":unresolved,
            "restart_clear":False,"entry_permitted":False,
            "execution_enabled":False,"broker_writes":0}
