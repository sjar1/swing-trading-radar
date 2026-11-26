"""Read-only restart admission gate; never authorizes broker writes."""
from intraday_alpaca_fills import FillHistoryBlocked

def inspect_restart(*, account_verified, position_count, open_order_count,
                    history_complete=False, attribution_certified=False):
    if type(account_verified) is not bool or type(position_count) is not int or type(open_order_count) is not int:
        raise FillHistoryBlocked("invalid_restart_snapshot")
    if position_count<0 or open_order_count<0:
        raise FillHistoryBlocked("invalid_restart_snapshot")
    if type(history_complete) is not bool or type(attribution_certified) is not bool:
        raise FillHistoryBlocked("invalid_restart_snapshot")
    reasons=[]
    if not account_verified:reasons.append("account_not_verified")
    if position_count:reasons.append("positions_require_attribution")
    if open_order_count:reasons.append("open_orders_require_reconciliation")
    if not history_complete:reasons.append("history_not_certified")
    if not attribution_certified:reasons.append("attribution_not_certified")
    return {"restart_clear":not reasons,"blockers":reasons,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
