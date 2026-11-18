"""Sanitized read-only PAPER/database restart diagnostic; no order submissions."""
import json,os,sys
from datetime import datetime,timezone
from intraday_engine import api,PAPER
from intraday_recovery_readiness import inspect_recovery
from intraday_durable_fill_reconciliation import load_session_intents

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
        result=inspect_recovery(db_url=os.environ["INTRADAY_DATABASE_URL"],
            session_date=datetime.now(timezone.utc).date(),api_fn=api,base=PAPER,
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
