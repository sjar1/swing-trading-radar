"""Read-only combined recovery and bounded-history observation.

Window consistency is NOT lifetime completeness or execution certification.
"""
from datetime import datetime,timezone,timedelta
from intraday_recovery_readiness import inspect_recovery
from intraday_account_history import collect_window
from intraday_history_coverage import inspect_coverage
from intraday_durable_fill_reconciliation import reconcile_session
from intraday_alpaca_fills import FillHistoryBlocked

def inspect_bundle(*,db_url,session_date,api_fn,base,expected_account_id,
                   now,load_fn,history_fn=collect_window):
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise FillHistoryBlocked("invalid_observation_time")
    now=now.astimezone(timezone.utc)
    recovery=inspect_recovery(db_url=db_url,session_date=session_date,
        api_fn=api_fn,base=base,expected_account_id=expected_account_id,
        load_fn=load_fn)
    start=now-timedelta(hours=1)
    window=history_fn(api_fn=api_fn,base=base,start_utc=start,end_utc=now,
                      max_pages=10,clock_fn=lambda:now)
    coverage=inspect_coverage(windows=[window],required_start=start,required_end=now)
    if not coverage["requested_window_covered"]:
        raise FillHistoryBlocked("history_window_gap")
    intents=load_fn(db_url,session_date.isoformat())
    if not isinstance(intents,list):
        raise FillHistoryBlocked("invalid_durable_intents")
    consistency=reconcile_session(intents,window["fills"])
    blockers=list(recovery["blockers"])
    blockers.append("account_lifetime_history_unverified")
    return {"status":"bounded_history_and_recovery_observed",
        "account_identity_verified":recovery["account_identity_verified"],
        "open_order_count":recovery["open_order_count"],
        "position_count":recovery["position_count"],
        "window_fill_count":window["activity_count"],
        "window_coverage_verified":True,
        "window_fill_consistency_verified":consistency["session_consistency_verified"],
        "blockers":blockers,"restart_clear":False,
        "account_history_complete":False,"position_attribution_certified":False,
        "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
