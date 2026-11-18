"""Fail-closed summary of bounded PAPER recovery observations.

A healthy diagnostic is NOT trading authorization. No broker or database writes.
"""
from intraday_durable_fill_reconciliation import DurableFillBlocked

def assess(*,snapshot,audit,broker_probe,execution_comparison):
    if not all(isinstance(x,dict) for x in (snapshot,audit,broker_probe,execution_comparison)):
        raise DurableFillBlocked("invalid_recovery_evidence")
    intents=snapshot.get("intents")
    if not isinstance(intents,list) or snapshot.get("snapshot_atomic") is not True:
        raise DurableFillBlocked("non_atomic_recovery_evidence")
    n=len(intents)
    if audit.get("intent_count")!=n or broker_probe.get("durable_intent_count")!=n or execution_comparison.get("durable_intent_count")!=n:
        raise DurableFillBlocked("recovery_evidence_intent_count_mismatch")
    for evidence in (broker_probe,execution_comparison):
        if evidence.get("execution_enabled") is not False or evidence.get("broker_writes")!=0:
            raise DurableFillBlocked("unsafe_recovery_evidence")
    matched=broker_probe.get("matched_broker_orders")
    unresolved=broker_probe.get("unresolved_broker_orders")
    compared=execution_comparison.get("compared_order_count")
    incomplete=execution_comparison.get("incomplete_order_count")
    drift=execution_comparison.get("broker_snapshot_drift_count")
    pending=execution_comparison.get("unresolved_broker_order_count")
    if any(type(x) is not int or x<0 for x in (matched,unresolved,compared,incomplete,drift,pending)):
        raise DurableFillBlocked("invalid_recovery_evidence_counts")
    if matched+unresolved!=n or compared+incomplete!=n or drift>incomplete or pending>incomplete:
        raise DurableFillBlocked("inconsistent_recovery_evidence_counts")
    # A bounded probe cannot establish account-wide history, restart readiness,
    # or permission to place orders. Reject any upstream claim to the contrary.
    forbidden_true=("entry_permitted","restart_clear","account_history_complete",
                    "fill_history_certified","historical_execution_coverage_proven",
                    "position_attribution_certified","broker_history_exhaustive")
    for evidence in (broker_probe,execution_comparison):
        if any(evidence.get(flag) is True for flag in forbidden_true):
            raise DurableFillBlocked("unsupported_recovery_authorization_claim")
    observed_fills=broker_probe.get("broker_orders_with_fills")
    compared_matched=execution_comparison.get("matched_broker_orders")
    if type(observed_fills) is not int or type(compared_matched) is not int or not (0<=observed_fills<=matched<=n) or not (0<=compared_matched<=n):
        raise DurableFillBlocked("invalid_broker_observation_counts")
    if compared>compared_matched:
        raise DurableFillBlocked("comparison_exceeds_matched_broker_orders")
    clean=n>0 and unresolved==0 and incomplete==0 and drift==0 and pending==0
    return {"status":"bounded_recovery_observed" if clean else "recovery_evidence_incomplete",
            "nonempty_durable_session_observed":n>0,
            "bounded_observations_consistent":clean,
            "account_history_complete":False,
            "historical_execution_coverage_proven":False,
            "position_attribution_certified":False,
            "restart_clear":False,"entry_permitted":False,
            "execution_enabled":False,"broker_writes":0}
