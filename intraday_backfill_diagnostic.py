"""Sanitized bounded PAPER history probe; read-only and never certifies execution."""
import json,os,sys
from datetime import datetime,timezone,timedelta
from intraday_engine import api,PAPER
from intraday_history_backfill import inspect_backfill

def read_only_api(base,path,method="GET",payload=None):
    if base!=PAPER or method!="GET" or payload is not None or not path.startswith("/v2/"):
        raise ValueError("paper_read_only_required")
    return api(base,path)

def main():
    result={"status":"blocked","mode":"PAPER_READ_ONLY","entry_permitted":False,
            "execution_enabled":False,"broker_writes":0}
    if not all(os.getenv(k) for k in ("ALPACA_INTRADAY_API_KEY",
                                     "ALPACA_INTRADAY_API_SECRET")):
        result["reason"]="missing_paper_credentials"
        print(json.dumps(result,sort_keys=True))
        return 2
    try:
        hours=int(os.getenv("INTRADAY_BACKFILL_HOURS","6"))
        if not 1<=hours<=24:
            raise ValueError("invalid_backfill_hours")
        end=datetime.now(timezone.utc)-timedelta(minutes=2)
        start=end-timedelta(hours=hours)
        result.update(inspect_backfill(api_fn=read_only_api,base=PAPER,
            start_utc=start,end_utc=end,max_windows=24))
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception as exc:
        result["reason"]=type(exc).__name__
        print(json.dumps(result,sort_keys=True))
        return 3
if __name__=="__main__":sys.exit(main())
