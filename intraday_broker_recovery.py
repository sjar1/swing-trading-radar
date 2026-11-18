"""Read-only recovery of ambiguous PAPER submissions by exact client order ID.

Never resubmits orders. A missing broker order is NOT proof of non-submission.
"""
from urllib.parse import quote
from intraday_engine import api,PAPER

class RecoveryBlocked(RuntimeError):
    pass

def decide(client_id,ledger_state,broker_order):
    if not isinstance(client_id,str) or not client_id.startswith("intraday-"):
        raise RecoveryBlocked("invalid_client_id")
    if ledger_state not in ("unknown","submitted","accepted","partially_filled","filled","canceled","rejected","expired","closed"):
        raise RecoveryBlocked("invalid_recovery_state")
    if broker_order is None:
        return {"reconciled":False,"reason":"broker_order_not_found_ambiguous",
                "retry_submission":False,"execution_enabled":False}
    if not isinstance(broker_order,dict) or broker_order.get("client_order_id")!=client_id or not broker_order.get("id"):
        raise RecoveryBlocked("broker_identity_mismatch")
    status=broker_order.get("status")
    states={"new":"accepted","accepted":"accepted","pending_new":"submitted",
            "partially_filled":"partially_filled","filled":"filled",
            "canceled":"canceled","expired":"expired","rejected":"rejected"}
    if status not in states:
        return {"reconciled":False,"reason":"unrecognized_or_pending_broker_status",
                "retry_submission":False,"execution_enabled":False}
    return {"reconciled":True,"broker_order_id":broker_order["id"],
            "broker_status":status,"suggested_state":states[status],
            "retry_submission":False,"execution_enabled":False}

def inspect(client_id,ledger_state):
    if ledger_state not in ("unknown","submitted","accepted","partially_filled"):
        raise RecoveryBlocked("not_recoverable_state")
    if not isinstance(client_id,str) or not client_id.startswith("intraday-"):
        raise RecoveryBlocked("invalid_client_id")
    try:
        order=api(PAPER,"/v2/orders:by_client_order_id?client_order_id="+quote(client_id,safe=""))
    except Exception:
        # Network errors, including 404, do not authorize a second submission.
        return decide(client_id,ledger_state,None)
    return decide(client_id,ledger_state,order)
