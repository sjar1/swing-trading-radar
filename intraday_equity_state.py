"""Pure, fail-closed daily equity high-water-mark state transitions.

A future execution service must persist state transactionally and atomically
before enabling orders. This module never submits broker requests.
"""
import math
from datetime import datetime

class EquityStateBlocked(ValueError):
    pass

def amount(value):
    if isinstance(value, bool):
        raise EquityStateBlocked("invalid_amount")
    try:
        number=float(value)
    except (ValueError, TypeError):
        raise EquityStateBlocked("invalid_amount")
    if not math.isfinite(number) or number < 0:
        raise EquityStateBlocked("invalid_amount")
    return number

def update_equity_state(previous, session_date, equity, prior_close_equity, sampled_at):
    """Return a new immutable-in-practice snapshot; never silently reset an old day."""
    if not isinstance(session_date,str):
        raise EquityStateBlocked("invalid_session")
    try:
        if datetime.strptime(session_date,"%Y-%m-%d").strftime("%Y-%m-%d")!=session_date:
            raise ValueError()
    except ValueError:
        raise EquityStateBlocked("invalid_session")
    if not isinstance(sampled_at,datetime) or sampled_at.tzinfo is None or sampled_at.utcoffset() is None:
        raise EquityStateBlocked("invalid_timestamp")
    if sampled_at.date().isoformat()!=session_date and sampled_at.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date().isoformat()!=session_date:
        raise EquityStateBlocked("timestamp_session_mismatch")
    current=amount(equity)
    close=amount(prior_close_equity)
    if current<=0 or close<=0:
        raise EquityStateBlocked("invalid_equity")
    if previous is None:
        raise EquityStateBlocked("missing_durable_prior_state")
    if not isinstance(previous,dict) or previous.get("version")!=1 or previous.get("session_date")!=session_date:
        raise EquityStateBlocked("invalid_or_stale_state")
    peak=amount(previous.get("peak_equity"))
    stored_close=amount(previous.get("prior_close_equity"))
    if abs(stored_close-close)>0.01:
        raise EquityStateBlocked("prior_close_mismatch")
    old_time=previous.get("sampled_at")
    try:
        old_dt=datetime.fromisoformat(old_time)
    except (TypeError,ValueError):
        raise EquityStateBlocked("invalid_stored_timestamp")
    if old_dt.tzinfo is None or old_dt.utcoffset() is None or sampled_at<old_dt:
        raise EquityStateBlocked("out_of_order_sample")
    high=max(peak,current)
    drawdown=max(0,high-current,close-current)
    return {"version":1,"session_date":session_date,"prior_close_equity":close,
            "peak_equity":high,"last_equity":current,
            "sampled_at":sampled_at.isoformat(),"drawdown":round(drawdown,2),
            "blocked":drawdown>=100.0}

def initial_state(session_date, prior_close_equity, sampled_at):
    """Bootstrap only for a verified flat, no-trades session by external caller."""
    close=amount(prior_close_equity)
    if close<=0 or not isinstance(sampled_at,datetime) or sampled_at.tzinfo is None:
        raise EquityStateBlocked("invalid_bootstrap")
    if sampled_at.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date().isoformat()!=session_date:
        raise EquityStateBlocked("invalid_bootstrap_session")
    return {"version":1,"session_date":session_date,"prior_close_equity":close,
            "peak_equity":close,"last_equity":close,"sampled_at":sampled_at.isoformat(),
            "drawdown":0.0,"blocked":False}
