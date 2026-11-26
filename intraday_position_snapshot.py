"""Fail-closed, read-only broker snapshot checks. Never certifies ownership."""
from decimal import Decimal, InvalidOperation
from intraday_alpaca_fills import FillHistoryBlocked

def inspect_positions(*, api_fn, base):
    positions=api_fn(base,"/v2/positions")
    if not isinstance(positions,list):
        raise FillHistoryBlocked("invalid_positions_snapshot")
    seen=set()
    for position in positions:
        if not isinstance(position,dict):
            raise FillHistoryBlocked("invalid_position")
        symbol=position.get("symbol")
        if not isinstance(symbol,str) or not symbol or symbol in seen:
            raise FillHistoryBlocked("invalid_or_duplicate_position_symbol")
        seen.add(symbol)
        try:
            qty=Decimal(str(position["qty"]))
        except (KeyError,TypeError,ValueError,InvalidOperation):
            raise FillHistoryBlocked("invalid_position_quantity") from None
        if not qty.is_finite() or qty==0:
            raise FillHistoryBlocked("invalid_position_quantity")
    return {"position_count":len(positions),"positions_observed":True,
            "position_attribution_certified":False,"account_history_complete":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
