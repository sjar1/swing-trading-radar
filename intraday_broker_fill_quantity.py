"""Fail-closed broker cumulative fill comparison for persisted order journals."""
from decimal import Decimal,InvalidOperation
from intraday_persistent_recovery_simulator import PersistenceBlocked

def quantity(value):
    if isinstance(value,bool) or value is None:
        raise PersistenceBlocked("invalid_broker_fill_quantity")
    try: result=Decimal(str(value))
    except (ValueError,TypeError,InvalidOperation) as exc:
        raise PersistenceBlocked("invalid_broker_fill_quantity") from exc
    if not result.is_finite() or result<0:
        raise PersistenceBlocked("invalid_broker_fill_quantity")
    return result

def compare(*,persisted_quantity,broker_order,phase):
    if not isinstance(broker_order,dict) or phase not in (
        "submission_unknown","needs_reconciliation","acknowledged",
        "partially_filled","filled","canceled","rejected"):
        raise PersistenceBlocked("invalid_fill_comparison")
    saved=quantity(persisted_quantity)
    broker=quantity(broker_order.get("filled_qty"))
    if broker!=saved:
        raise PersistenceBlocked("broker_persisted_fill_quantity_mismatch")
    if phase=="filled" and broker<=0:
        raise PersistenceBlocked("filled_without_quantity")
    if phase in ("acknowledged","rejected") and saved!=0:
        raise PersistenceBlocked("unexpected_persisted_fill")
    return {"status":"broker_fill_quantity_observed",
            "quantity_equal":True,"fill_history_certified":False,
            "restart_clear":False,"entry_permitted":False,
            "execution_enabled":False,"broker_writes":0}
