"""Read-only Alpaca PAPER / Supabase audit. Never modifies broker or database."""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

PREFIX = "intraday-"

def compare(session, intents, broker_orders, positions, history_complete=True):
    """Fail closed on missing records, foreign positions, and uncertain snapshots."""
    problems = []
    if not history_complete:
        problems.append("broker_history_incomplete")
    if session is None:
        problems.append("durable_session_missing")
    elif session[0] is not True:
        problems.append("durable_session_blocked")
    if not isinstance(intents, list) or not isinstance(broker_orders, list) or not isinstance(positions, list):
        return {"safe_to_trade": False, "problems": ["invalid_snapshot"]}
    by_client = {}
    for intent in intents:
        if not isinstance(intent, (tuple, list)) or len(intent) != 2 or not isinstance(intent[0], str):
            problems.append("invalid_intent")
            continue
        if intent[0] in by_client:
            problems.append("duplicate_intent")
        by_client[intent[0]] = intent[1]
    broker = {}
    for order in broker_orders:
        if not isinstance(order, dict) or not isinstance(order.get("client_order_id"), str):
            problems.append("invalid_broker_order")
            continue
        client = order["client_order_id"]
        if client in broker:
            problems.append("duplicate_broker_client_id")
        broker[client] = order
        if client.startswith(PREFIX) and client not in by_client:
            problems.append("untracked_intraday_broker_order")
        if not client.startswith(PREFIX):
            problems.append("foreign_order_in_dedicated_account")
    for client, state in by_client.items():
        order = broker.get(client)
        if order is None:
            # A missing order can be an unsubmitted intent or an ambiguous broker acknowledgement.
            problems.append("intent_without_broker_order")
        elif state not in ("reserved","submitted","accepted","partially_filled",
                           "filled","canceled","rejected","expired","closed","unknown"):
            problems.append("unknown_intent_state")
    if positions:
        problems.append("position_attribution_unverified")
    return {"safe_to_trade": False, "problems": sorted(set(problems)),
            "intent_count": len(by_client), "broker_order_count": len(broker),
            "position_count": len(positions),
            "execution_enabled": False}

def main():
    if not os.getenv("INTRADAY_DATABASE_URL"):
        print("BLOCKED: database secret missing")
        return 2
    if not all(os.getenv(k) for k in ("ALPACA_INTRADAY_API_KEY","ALPACA_INTRADAY_API_SECRET")):
        print("BLOCKED: paper account secrets missing")
        return 2
    try:
        import psycopg
        from intraday_engine import api, PAPER
        from urllib.parse import quote
        now = datetime.now(ZoneInfo("America/New_York"))
        day = now.date().isoformat()
        # Read-only transaction. Session is never bootstrapped or unblocked by this audit.
        with psycopg.connect(os.environ["INTRADAY_DATABASE_URL"], connect_timeout=8, sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT NOT trading_blocked FROM intraday_paper.sessions WHERE session_date=%s", (day,))
                session = cur.fetchone()
                cur.execute("SELECT client_order_id,state FROM intraday_paper.order_intents WHERE session_date=%s", (day,))
                intents = cur.fetchall()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(__import__("datetime").timezone.utc).isoformat()
        orders = api(PAPER, "/v2/orders?status=all&limit=500&nested=false&after="+quote(start))
        positions = api(PAPER, "/v2/positions")
        # A full page could mean additional unseen orders. Fail closed.
        complete = isinstance(orders, list) and len(orders) < 500
        result = compare(session, intents, orders, positions, history_complete=complete)
        print(json.dumps({"date": day, **result}, sort_keys=True))
        # This is an observational audit; missing session is expected before bootstrap.
        # Fail the job for unreadable snapshots or incomplete history.
        return 3 if any(p in result["problems"] for p in
               ("invalid_snapshot","broker_history_incomplete","invalid_intent","invalid_broker_order")) else 0
    except Exception as exc:
        print(f"BLOCKED: reconciliation audit failed ({type(exc).__name__})")
        return 3

if __name__ == "__main__":
    sys.exit(main())
