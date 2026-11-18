"""Read-only independent session reconciliation health evaluator.

A consistency result does not prove complete account history or position
ownership. No green heartbeat without explicitly complete independent evidence.
"""
from datetime import datetime,timezone

class ReconciliationHealthBlocked(RuntimeError):
    pass

def evaluate(evidence,*,now,max_age_seconds=90):
    if not isinstance(evidence,dict) or not isinstance(now,datetime) or now.tzinfo is None:
        raise ReconciliationHealthBlocked("invalid_evidence")
    if type(max_age_seconds)!=int or not 1<=max_age_seconds<=300:
        raise ReconciliationHealthBlocked("invalid_freshness")
    observed=evidence.get("observed_at")
    if not isinstance(observed,str):
        raise ReconciliationHealthBlocked("missing_observation_timestamp")
    try:
        timestamp=datetime.fromisoformat(observed.replace("Z","+00:00"))
    except ValueError:
        raise ReconciliationHealthBlocked("invalid_observation_timestamp")
    if timestamp.tzinfo is None:
        raise ReconciliationHealthBlocked("naive_observation_timestamp")
    age=(now.astimezone(timezone.utc)-timestamp.astimezone(timezone.utc)).total_seconds()
    if age<0 or age>max_age_seconds:
        raise ReconciliationHealthBlocked("stale_evidence")
    required=("session_history_exhausted","session_consistency_verified",
              "account_history_complete","position_attribution_certified",
              "broker_snapshot_complete","durable_intents_verified")
    missing=[key for key in required if evidence.get(key) is not True]
    if missing:
        raise ReconciliationHealthBlocked("insufficient_independent_evidence")
    if evidence.get("unmatched_fills")!=0 or evidence.get("unattributed_positions")!=0:
        raise ReconciliationHealthBlocked("unreconciled_activity")
    return {"reconciliation_observed":True,"healthy":True,"entry_permitted":False,
            "execution_enabled":False,"broker_writes":0}
