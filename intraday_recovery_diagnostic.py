"""Sanitized read-only PAPER/database restart diagnostic; no order submissions."""
import json,os,sys
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from intraday_observation_bundle import inspect_bundle
from intraday_engine import api,PAPER
from intraday_recovery_readiness import inspect_recovery
from intraday_durable_fill_reconciliation import load_session_intents

def read_only_api(base,path,method="GET",payload=None):
    if base!=PAPER or method!="GET" or payload is not None or not path.startswith("/v2/"):
        raise ValueError("read_only_paper_endpoint_required")
    return api(base,path)

def main():
    output={"status":"blocked","mode":"PAPER_READ_ONLY","entry_permitted":False,
            "execution_enabled":False,"broker_writes":0}
    if not os.getenv("INTRADAY_DATABASE_URL"):
        output["reason"]="missing_database_url"
        print(json.dumps(output,sort_keys=True))
        return 2
    if not os.getenv("ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID") or not all(
        os.getenv(k) for k in ("ALPACA_INTRADAY_API_KEY","ALPACA_INTRADAY_API_SECRET")):
        output["reason"]="missing_paper_identity_or_credentials"
        print(json.dumps(output,sort_keys=True))
        return 2
    try:
        result=inspect_bundle(db_url=os.environ["INTRADAY_DATABASE_URL"],
            session_date=datetime.now(ZoneInfo("America/New_York")).date(),
            now=datetime.now(timezone.utc),api_fn=read_only_api,base=PAPER,
            expected_account_id=os.environ["ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID"],
            load_fn=load_session_intents)
        output.update(result)
        output["mode"]="PAPER_READ_ONLY"
        print(json.dumps(output,sort_keys=True))
        return 0
    except Exception as exc:
        # Never emit account IDs, DB URLs, SQL errors, broker payloads or raw exceptions.
        output["reason"]=type(exc).__name__
        print(json.dumps(output,sort_keys=True))
        return 3
if __name__=="__main__":sys.exit(main())
