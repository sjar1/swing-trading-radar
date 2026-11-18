"""Fail-closed PAPER-only order pilot. Never invoked by scheduled scanners.

This module prepares and validates a single bracket order, but does not submit it.
A later independently reviewed execution adapter must handle reconciliation,
durable risk state, fills, market calendar, and EOD flattening.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from intraday_engine import PAPER, RISK, DAILY_LOSS, MAX_EXPOSURE, finite

NY = ZoneInfo("America/New_York")
MAX_PILOT_NOTIONAL = 250.0
PILOT_SYMBOLS = frozenset(("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD"))

class PilotBlocked(ValueError):
    pass

def prepare_pilot(symbol, trade, account, positions, open_orders, now=None):
    """Pure function: return proposed bracket payload, with no network side effects."""
    now = now or datetime.now(NY)
    now = now.astimezone(NY)
    if now.weekday() >= 5 or not time(9, 45) <= now.time() < time(15, 0):
        raise PilotBlocked("outside_pilot_window")
    if symbol not in PILOT_SYMBOLS:
        raise PilotBlocked("symbol_not_allowed")
    if account.get("status") != "ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
        raise PilotBlocked("account_not_active")
    equity, previous, cash = (finite(account.get(k)) for k in ("equity", "last_equity", "cash"))
    if any(v is None for v in (equity, previous, cash)) or equity <= 0 or cash < 0:
        raise PilotBlocked("unknown_account_risk")
    if previous - equity >= DAILY_LOSS:
        raise PilotBlocked("daily_loss_limit")
    if positions or open_orders:
        raise PilotBlocked("pilot_requires_empty_account")
    if not isinstance(trade, dict):
        raise PilotBlocked("invalid_trade")
    try:
        qty = trade["qty"]
        price = finite(trade["limit_price"])
        stop = finite(trade["stop_loss"]["stop_price"])
        target = finite(trade["take_profit"]["limit_price"])
    except (KeyError, TypeError):
        raise PilotBlocked("invalid_trade")
    if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
        raise PilotBlocked("invalid_quantity")
    if any(v is None for v in (price, stop, target)) or not (0 < stop < price < target):
        raise PilotBlocked("invalid_prices")
    notional = qty * price
    risk = qty * (price - stop)
    if risk > RISK + 0.001 or notional > min(MAX_PILOT_NOTIONAL, cash, MAX_EXPOSURE):
        raise PilotBlocked("pilot_risk_limit")
    if target - price < 2.99 * (price - stop):
        raise PilotBlocked("reward_risk_limit")
    return {
        "symbol": symbol, "qty": str(qty), "side": "buy", "type": "limit",
        "time_in_force": "day", "limit_price": f"{price:.2f}",
        "order_class": "bracket",
        "take_profit": {"limit_price": f"{target:.2f}"},
        "stop_loss": {"stop_price": f"{stop:.2f}"},
        "paper_endpoint": PAPER,
        "execution_enabled": False,
    }
