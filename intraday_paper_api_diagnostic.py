"""Read-only Alpaca PAPER history API shape and pagination diagnostic.

Never emits account IDs, order IDs, fill payloads, secrets or broker errors.
Never certifies complete history or authorizes execution.
"""
import json,os,sys
from datetime import datetime,timezone,timedelta
from intraday_engine import api,PAPER
from intraday_account_history import collect_window
from intraday_alpaca_fills import FillHistoryBlocked
from intraday_account_identity import verify_account_identity,AccountIdentityBlocked

def inspect(*,api_fn,now,expected_account_id=None):
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise FillHistoryBlocked("invalid_observation_time")
    now=now.astimezone(timezone.utc)
    if not callable(api_fn):
        raise FillHistoryBlocked("invalid_api")
    identity=verify_account_identity(api_fn=api_fn,base=PAPER,expected_account_id=expected_account_id)
    # A short fixed UTC window limits exposure to API pagination edge cases.
    start=now-timedelta(hours=1)
    snapshot=collect_window(api_fn=api_fn,base=PAPER,start_utc=start,end_utc=now,max_pages=10,clock_fn=lambda:now)
    return {"mode":"PAPER_READ_ONLY","status":"window_observed",
            "account_identity_verified":identity["account_identity_verified"],
            "dedicated_account_proven":False,
            "window_exhausted":True,"activity_count":snapshot["activity_count"],
            "order_count":snapshot["orders_count"],
            "account_history_complete":False,
            "position_attribution_certified":False,
            "reconciliation_heartbeat_healthy":False,
            "execution_enabled":False,"entry_permitted":False,"broker_writes":0}

def main():
    output={"mode":"PAPER_READ_ONLY","status":"blocked",
            "account_history_complete":False,"position_attribution_certified":False,
            "reconciliation_heartbeat_healthy":False,"execution_enabled":False,
            "entry_permitted":False,"broker_writes":0}
    if not all(os.getenv(k) for k in ("ALPACA_INTRADAY_API_KEY","ALPACA_INTRADAY_API_SECRET")):
        output["reason"]="missing_paper_credentials"
        print(json.dumps(output,sort_keys=True))
        return 2
    try:
        output=inspect(api_fn=api,now=datetime.now(timezone.utc),
                       expected_account_id=os.getenv("ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID"))
        print(json.dumps(output,sort_keys=True))
        return 0
    except Exception as exc:
        output["reason"]=type(exc).__name__
        if isinstance(exc,AccountIdentityBlocked):
            safe_reasons={"expected_account_missing","invalid_account_snapshot","missing_broker_account_id","broker_account_mismatch","expected_value_is_account_number_not_id"}
            output["identity_failure"]=str(exc) if str(exc) in safe_reasons else "identity_check_failed"
        print(json.dumps(output,sort_keys=True))
        return 3

if __name__=="__main__":
    sys.exit(main())
