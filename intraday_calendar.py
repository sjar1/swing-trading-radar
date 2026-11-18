"""Conservative NYSE session-window controls for PAPER intraday trading.

Uses Alpaca's broker-supplied market calendar rather than hard-coded holidays.
No orders are submitted or canceled here.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

class CalendarBlocked(ValueError):
    pass

def session_window(calendar_day, now):
    """Validate a broker calendar day and compute entry/flatten deadlines.

    Expected broker calendar keys: date (YYYY-MM-DD), open (HH:MM),
    close (HH:MM). Ambiguity fails closed.
    """
    if not isinstance(calendar_day, dict) or not isinstance(now, datetime):
        raise CalendarBlocked("missing_calendar")
    if now.tzinfo is None or now.utcoffset() is None:
        raise CalendarBlocked("naive_clock")
    local = now.astimezone(NY)
    day = calendar_day.get("date")
    if not isinstance(day, str) or day != local.date().isoformat():
        raise CalendarBlocked("calendar_date_mismatch")
    try:
        opening = datetime.fromisoformat(day + "T" + calendar_day["open"]).replace(tzinfo=NY)
        closing = datetime.fromisoformat(day + "T" + calendar_day["close"]).replace(tzinfo=NY)
    except (TypeError, ValueError, KeyError):
        raise CalendarBlocked("invalid_calendar_hours")
    if opening.date() != closing.date() or not opening < closing:
        raise CalendarBlocked("invalid_session")
    if closing - opening > timedelta(hours=7) or closing - opening < timedelta(hours=2):
        raise CalendarBlocked("unexpected_session_length")
    entry_start = opening + timedelta(minutes=15)
    entry_end = min(closing - timedelta(minutes=45),
                    opening + timedelta(hours=5, minutes=45))
    flatten_start = closing - timedelta(minutes=30)
    return {
        "date": day,
        "open": opening.isoformat(),
        "close": closing.isoformat(),
        "entry_allowed": entry_start <= local < entry_end,
        "flatten_due": flatten_start <= local < closing,
        "past_close": local >= closing,
        "entry_start": entry_start.isoformat(),
        "entry_end": entry_end.isoformat(),
        "flatten_start": flatten_start.isoformat(),
    }

def verify_clock(calendar_day, broker_clock, now):
    """Require broker clock and market calendar to agree on the session."""
    window = session_window(calendar_day, now)
    if not isinstance(broker_clock, dict) or not isinstance(broker_clock.get("is_open"), bool):
        raise CalendarBlocked("missing_broker_clock")
    local = now.astimezone(NY)
    open_time = datetime.fromisoformat(window["open"])
    close_time = datetime.fromisoformat(window["close"])
    expected = open_time <= local < close_time
    if broker_clock["is_open"] != expected:
        raise CalendarBlocked("broker_clock_disagreement")
    return window
