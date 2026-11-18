"""Isolated PAPER intent reservation; no broker submission or authorization.

An uncertain submission must never be automatically retried.
"""
from datetime import date
from decimal import Decimal,InvalidOperation
from intraday_durable_fill_reconciliation import DurableFillBlocked

def reserve(*,db_url,session_date,client_order_id,symbol,strategy,reserved_risk,
            expected_account_verified,broker_base):
    if not isinstance(db_url,str) or not db_url or type(session_date) is not date or expected_account_verified is not True or broker_base!="https://paper-api.alpaca.markets":
        raise DurableFillBlocked("reservation_parameters_invalid")
    if not isinstance(client_order_id,str) or not client_order_id.startswith("intraday-") or len(client_order_id)>100:
        raise DurableFillBlocked("reservation_identity_invalid")
    if not isinstance(symbol,str) or not symbol.isalpha() or not symbol.isupper() or len(symbol)>8 or strategy not in ("opening_range_breakout","vwap_reclaim"):
        raise DurableFillBlocked("reservation_strategy_invalid")
    try: risk=Decimal(str(reserved_risk))
    except (TypeError,ValueError,InvalidOperation): raise DurableFillBlocked("reservation_risk_invalid") from None
    if not risk.is_finite() or not Decimal("0")<risk<=Decimal("25"):
        raise DurableFillBlocked("reservation_risk_invalid")
    import psycopg
    try:
        with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT trading_blocked FROM intraday_paper.sessions
                               WHERE session_date=%s FOR UPDATE""",(session_date,))
                session=cur.fetchone()
                if session is None or session[0] is not True:
                    raise DurableFillBlocked("session_not_explicitly_blocked")
                cur.execute("""SELECT COUNT(*) FROM intraday_paper.order_intents
                               WHERE session_date=%s""",(session_date,))
                count=cur.fetchone()
                if count is None or type(count[0]) is not int or count[0]!=0:
                    raise DurableFillBlocked("existing_intents_block_reservation")
                cur.execute("""INSERT INTO intraday_paper.order_intents
                               (client_order_id,session_date,symbol,strategy,reserved_risk,state)
                               VALUES (%s,%s,%s,%s,%s,'reserved')""",
                            (client_order_id,session_date,symbol,strategy,risk))
        return {"status":"durable_intent_reserved","client_order_id":client_order_id,
                "manual_approval_required":True,"submission_allowed":False,
                "retry_submission":False,"restart_clear":False,
                "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
    except DurableFillBlocked:
        raise
    except Exception as exc:
        # No automatic retry on commit ambiguity or any database failure.
        raise DurableFillBlocked("reservation_outcome_unknown_reconcile_before_retry") from exc
