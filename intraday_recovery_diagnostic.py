"""Sanitized read-only PAPER/database restart diagnostic; no order submissions."""
import json,os,sys
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from intraday_observation_bundle import inspect_bundle
from intraday_engine import api,PAPER
from intraday_recovery_readiness import inspect_recovery
from intraday_durable_fill_reconciliation import load_session_intents
from intraday_durable_event_audit import load_order_event_rows,audit_rows
from intraday_live_order_probe import inspect_orders
from intraday_snapshot_consistency import verify_snapshots
from intraday_durable_execution_comparison import compare_rows
from intraday_atomic_recovery_snapshot import load_atomic_snapshot
from intraday_recovery_evidence_assessment import assess

def read_only_api(base,path,method="GET",payload=None):
    if base!=PAPER or method!="GET" or payload is not None or not path.startswith("/v2/"):
        raise ValueError("read_only_paper_endpoint_required")
    return api(base,path)

def enforce_read_only(output):
    # Sanitized reporting invariant, including failed diagnostics.
    output.update({"mode":"PAPER_READ_ONLY","entry_permitted":False,
                   "execution_enabled":False,"broker_writes":0,
                   "restart_clear":False,"account_history_complete":False,
                   "position_attribution_certified":False})
    return output

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
        session_date=datetime.now(ZoneInfo("America/New_York")).date()
        observed_at=datetime.now(timezone.utc)
        result=inspect_bundle(db_url=os.environ["INTRADAY_DATABASE_URL"],
            session_date=session_date,
            now=observed_at,api_fn=read_only_api,base=PAPER,
            expected_account_id=os.environ["ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID"],
            load_fn=load_session_intents)
        output.update(result)
        snapshot=load_atomic_snapshot(os.environ["INTRADAY_DATABASE_URL"],session_date.isoformat())
        output["durable_snapshot_atomic"]=snapshot["snapshot_atomic"]
        event_rows=snapshot["event_rows"]
        audit=audit_rows(event_rows)
        output["durable_event_audit"]=audit
        intents=snapshot["intents"]
        output["durable_snapshot_consistency"]=verify_snapshots(event_rows=event_rows,intents=intents)
        output["broker_order_probe"]=inspect_orders(
            intents=intents,
            api_fn=read_only_api,base=PAPER)
        output["durable_execution_comparison"]=compare_rows(
            rows=snapshot["execution_rows"],
            api_fn=read_only_api,base=PAPER)
        if output["durable_execution_comparison"]["durable_intent_count"]!=len(intents):
            raise ValueError("durable_execution_snapshot_mismatch")
        if audit["intent_count"]!=output["broker_order_probe"]["durable_intent_count"]:
            raise ValueError("durable_intent_snapshot_mismatch")
        output["recovery_evidence_assessment"]=assess(
            snapshot=snapshot,audit=audit,
            broker_probe=output["broker_order_probe"],
            execution_comparison=output["durable_execution_comparison"])
        enforce_read_only(output)
        print(json.dumps(output,sort_keys=True))
        return 0
    except Exception as exc:
        # Never emit account IDs, DB URLs, SQL errors, broker payloads or raw exceptions.
        enforce_read_only(output)
        output["reason"]=type(exc).__name__
        print(json.dumps(output,sort_keys=True))
        return 3
if __name__=="__main__":sys.exit(main())
