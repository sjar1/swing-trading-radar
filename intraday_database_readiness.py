"""Read-only isolated database readiness diagnostic; never migrates or trades."""
import json,os,sys
from datetime import datetime,timezone
from intraday_durable_fill_reconciliation import load_session_intents,DurableFillBlocked

def inspect_database(*,db_url,session_date,load_fn=load_session_intents):
    if not isinstance(db_url,str) or not db_url.strip():
        raise DurableFillBlocked("database_url_missing")
    if not isinstance(session_date,str) or len(session_date)!=10:
        raise DurableFillBlocked("invalid_session_date")
    try:
        parsed=datetime.strptime(session_date,"%Y-%m-%d")
    except ValueError:
        raise DurableFillBlocked("invalid_session_date") from None
    if parsed.strftime("%Y-%m-%d")!=session_date:
        raise DurableFillBlocked("invalid_session_date")
    rows=load_fn(db_url,session_date)
    if not isinstance(rows,list):
        raise DurableFillBlocked("invalid_intent_snapshot")
    seen=set()
    for row in rows:
        if not isinstance(row,(list,tuple)) or len(row)!=3:
            raise DurableFillBlocked("invalid_durable_intent")
        client,symbol,broker_id=row
        if not isinstance(client,str) or not client.startswith("intraday-") or not isinstance(symbol,str) or not symbol or (broker_id is not None and (not isinstance(broker_id,str) or not broker_id)):
            raise DurableFillBlocked("invalid_durable_intent")
        if client in seen:raise DurableFillBlocked("duplicate_durable_intent")
        seen.add(client)
    return {"status":"database_readable","durable_intent_count":len(rows),
            "account_history_complete":False,"position_attribution_certified":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}

def main():
    result={"status":"blocked","execution_enabled":False,"broker_writes":0}
    try:
        result=inspect_database(db_url=os.getenv("INTRADAY_DATABASE_URL"),
            session_date=datetime.now(timezone.utc).date().isoformat())
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception as exc:
        # Do not log database URLs, SQL errors, credentials or returned records.
        result["reason"]=type(exc).__name__
        print(json.dumps(result,sort_keys=True))
        return 3
if __name__=="__main__":sys.exit(main())
