"""Read-only Alpaca PAPER fill history diagnostic.

Reports only aggregate counts and a fail-closed status. Never emits broker
identifiers, account numbers, secrets, or raw payloads.
"""
import json
import os
import sys
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from intraday_alpaca_fills import collect_session_fills,FillHistoryBlocked

def summarize(snapshot):
    if not isinstance(snapshot,dict) or snapshot.get("session_history_exhausted") is not True:
        raise FillHistoryBlocked("session_history_not_exhausted")
    fills=snapshot.get("fills")
    if not isinstance(fills,list):
        raise FillHistoryBlocked("invalid_fills")
    return {"mode":"PAPER_READ_ONLY","status":"session_history_observed",
            "activity_count":len(fills),"order_count":snapshot.get("orders_count"),
            "session_history_exhausted":True,
            "account_history_complete":False,"position_attribution_certified":False,
            "execution_enabled":False,"broker_writes":0}

def main():
    result={"mode":"PAPER_READ_ONLY","status":"blocked","execution_enabled":False,
            "broker_writes":0,"account_history_complete":False,
            "position_attribution_certified":False}
    if not all(os.getenv(k) for k in ("ALPACA_INTRADAY_API_KEY","ALPACA_INTRADAY_API_SECRET")):
        result["reason"]="paper_credentials_missing"
        print(json.dumps(result,sort_keys=True))
        return 2
    try:
        today=datetime.now(ZoneInfo("America/New_York"))
        start=today.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
        snapshot=collect_session_fills(start)
        result=summarize(snapshot)
        from intraday_durable_fill_reconciliation import load_session_intents,reconcile_session
        db_url=os.getenv("INTRADAY_DATABASE_URL")
        if not db_url:
            raise RuntimeError("database_unavailable")
        intents=load_session_intents(db_url,today.date().isoformat())
        proof=reconcile_session(intents,snapshot["fills"])
        result.update(proof)
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception as exc:
        # Deliberately omit raw broker responses and exception text.
        result["reason"]=type(exc).__name__
        print(json.dumps(result,sort_keys=True))
        return 3

if __name__=="__main__":
    sys.exit(main())
