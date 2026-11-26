"""PostgreSQL PAPER-only reservation store. No broker order submission.

Sessions must be explicitly initialized from verified broker state by a future
reviewed bootstrap process. This module does not create or unblock sessions.
"""
from decimal import Decimal, InvalidOperation

class ReservationBlocked(RuntimeError):
    pass

def reserve(conn, session_date, client_order_id, symbol, strategy, risk):
    """Atomic, fail-closed reservation across separate GitHub Actions runners.

    Requires a pre-existing unblocked session; locks the session row to serialize
    reservations and prevent simultaneous daily risk-budget oversubscription.
    """
    if not isinstance(client_order_id, str) or not client_order_id.startswith("intraday-"):
        raise ReservationBlocked("invalid_order_id")
    if not isinstance(symbol, str) or not symbol.isupper() or not symbol.isalpha() or len(symbol) > 8:
        raise ReservationBlocked("invalid_symbol")
    if strategy not in ("opening_range_breakout", "vwap_reclaim"):
        raise ReservationBlocked("invalid_strategy")
    try:
        amount = Decimal(str(risk))
    except (InvalidOperation, ValueError, TypeError):
        raise ReservationBlocked("invalid_risk")
    if not amount.is_finite() or amount <= 0 or amount > 25:
        raise ReservationBlocked("per_trade_risk_limit")
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT trading_blocked FROM intraday_paper.sessions "
                    "WHERE session_date=%s FOR UPDATE", (session_date,))
                row = cur.fetchone()
                if row is None or row[0] is not False:
                    raise ReservationBlocked("session_missing_or_blocked")
                cur.execute(
                    "SELECT count(*), coalesce(sum(reserved_risk),0) "
                    "FROM intraday_paper.order_intents WHERE session_date=%s",
                    (session_date,))
                count, used = cur.fetchone()
                if count >= 5:
                    raise ReservationBlocked("daily_entry_limit")
                if Decimal(str(used)) + amount > Decimal("100"):
                    raise ReservationBlocked("daily_risk_limit")
                cur.execute(
                    "INSERT INTO intraday_paper.order_intents "
                    "(client_order_id,session_date,symbol,strategy,reserved_risk) "
                    "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING "
                    "RETURNING client_order_id",
                    (client_order_id, session_date, symbol, strategy, amount))
                inserted = cur.fetchone()
                if inserted is None:
                    raise ReservationBlocked("duplicate_order_intent")
        return client_order_id
    except ReservationBlocked:
        raise
    except Exception as exc:
        raise ReservationBlocked("database_error_fail_closed") from exc

def execution_authorized():
    """Durable reservations alone do not authorize any broker order."""
    return False
