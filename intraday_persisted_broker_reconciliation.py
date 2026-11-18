"""Read-only persisted-event versus broker-order reconciliation.

A matching broker snapshot is observational only, never permission to retry
submission, flatten, or enable automated PAPER trading.
"""
from intraday_persistent_recovery_simulator import recover,PersistenceBlocked
from intraday_broker_recovery import decide,RecoveryBlocked

def reconcile(*,conn,client_order_id,broker_order):
    state=recover(conn,client_order_id)
    phase=state["phase"]
    phase_to_ledger={
        "submission_unknown":"unknown","needs_reconciliation":"unknown",
        "acknowledged":"accepted","partially_filled":"partially_filled",
        "filled":"filled","canceled":"canceled","rejected":"rejected",
    }
    if phase=="reserved":
        raise PersistenceBlocked("unsubmitted_intent_requires_manual_review")
    decision=decide(client_order_id,phase_to_ledger[phase],broker_order)
    if not decision["reconciled"]:
        return {"status":"unresolved_broker_order","reason":decision["reason"],
                "retry_submission":False,"restart_clear":False,
                "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
    # A persisted acknowledgement must match the broker's immutable ID.
    if phase not in ("submission_unknown","needs_reconciliation"):
        recover(conn,client_order_id,broker_order=broker_order)
    # Never equate a broker's cumulative fill status with persisted fill events.
    # Even matching statuses cannot establish complete account history.
    return {"status":"broker_identity_observed","persisted_phase":phase,
            "broker_status":decision["broker_status"],
            "persisted_fill_quantity":state["filled_quantity"],
            "broker_snapshot_complete":False,
            "fill_history_certified":False,"retry_submission":False,
            "restart_clear":False,"entry_permitted":False,
            "execution_enabled":False,"broker_writes":0}
