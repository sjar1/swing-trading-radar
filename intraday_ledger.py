"""Fail-closed durable intraday execution ledger primitives.

The ledger must be stored in a transactional persistent backend before any
execution adapter can be enabled. This module performs no broker writes.
"""
import hashlib
import json
from datetime import datetime, timezone

VERSION = 1
MAX_DAILY_ENTRIES = 5
MAX_DAILY_RISK = 100.0

class LedgerBlocked(ValueError):
    pass

def order_key(session_date, symbol, strategy, signal_bar):
    """Deterministic client-order identifier, stable across retries."""
    if not isinstance(session_date, str) or len(session_date) != 10:
        raise LedgerBlocked("invalid_session_date")
    try:
        if datetime.strptime(session_date, "%Y-%m-%d").strftime("%Y-%m-%d") != session_date:
            raise ValueError()
    except ValueError:
        raise LedgerBlocked("invalid_session_date")
    if not isinstance(symbol, str) or not symbol.isalpha() or len(symbol) > 8:
        raise LedgerBlocked("invalid_symbol")
    if not isinstance(strategy, str) or strategy not in ("opening_range_breakout", "vwap_reclaim"):
        raise LedgerBlocked("invalid_strategy")
    if not isinstance(signal_bar, str):
        raise LedgerBlocked("invalid_signal_bar")
    try:
        bar = datetime.fromisoformat(signal_bar.replace("Z", "+00:00"))
    except ValueError:
        raise LedgerBlocked("invalid_signal_bar")
    if bar.tzinfo is None or bar.utcoffset() is None:
        raise LedgerBlocked("naive_signal_bar")
    canonical = f"{session_date}|{symbol.upper()}|{strategy}|{bar.astimezone(timezone.utc).isoformat()}"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
    return f"intraday-{session_date.replace('-', '')}-{symbol.upper()}-{digest}"

def validate_ledger(ledger, session_date):
    if not isinstance(ledger, dict) or ledger.get("version") != VERSION:
        raise LedgerBlocked("missing_or_invalid_ledger")
    if ledger.get("session_date") != session_date:
        raise LedgerBlocked("session_mismatch")
    entries = ledger.get("entries")
    if not isinstance(entries, dict):
        raise LedgerBlocked("invalid_entries")
    if len(entries) > MAX_DAILY_ENTRIES:
        raise LedgerBlocked("entry_limit")
    total_risk = 0.0
    for key, entry in entries.items():
        if not isinstance(key, str) or not key.startswith("intraday-"):
            raise LedgerBlocked("invalid_order_key")
        if not isinstance(entry, dict) or entry.get("state") not in (
            "reserved", "submitted", "accepted", "partially_filled",
            "filled", "canceled", "rejected", "expired", "closed", "unknown"):
            raise LedgerBlocked("invalid_entry_state")
        risk = entry.get("reserved_risk")
        if isinstance(risk, bool) or not isinstance(risk, (int, float)) or not (0 <= risk <= 25):
            raise LedgerBlocked("invalid_reserved_risk")
        total_risk += risk
    if total_risk > MAX_DAILY_RISK:
        raise LedgerBlocked("risk_budget")
    return {"entry_count": len(entries), "reserved_risk": round(total_risk, 2)}

def propose_reservation(ledger, session_date, key, reserved_risk):
    """Return a proposed ledger mutation, never persist or submit it."""
    snapshot = validate_ledger(ledger, session_date)
    if not isinstance(key, str) or not key.startswith("intraday-"):
        raise LedgerBlocked("invalid_order_key")
    if key in ledger["entries"]:
        raise LedgerBlocked("duplicate_signal")
    if snapshot["entry_count"] >= MAX_DAILY_ENTRIES:
        raise LedgerBlocked("entry_limit")
    if isinstance(reserved_risk, bool) or not isinstance(reserved_risk, (int, float)) or not (0 < reserved_risk <= 25):
        raise LedgerBlocked("invalid_reserved_risk")
    if snapshot["reserved_risk"] + reserved_risk > MAX_DAILY_RISK:
        raise LedgerBlocked("risk_budget")
    updated = json.loads(json.dumps(ledger, allow_nan=False))
    updated["entries"][key] = {"state": "reserved", "reserved_risk": reserved_risk}
    validate_ledger(updated, session_date)
    return updated

def execution_ready(persistence_is_transactional, broker_reconciled, calendar_verified,
                    flattening_verified, peak_equity_durable):
    """Never allow execution until independent safeguards are verified."""
    return all((persistence_is_transactional, broker_reconciled, calendar_verified,
                flattening_verified, peak_equity_durable))
