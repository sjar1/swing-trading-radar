"""Conservative integrated reconciliation: coverage plus durable session evidence."""
from datetime import datetime
from intraday_history_coverage import inspect_coverage
from intraday_reconciliation_evidence import assemble,EvidenceBlocked
from intraday_restart_safety import inspect_restart

def assess(*,windows,required_start,required_end,session_snapshot,intents,
           positions,observed_at,account_verified,open_order_count,
           broker_snapshot_complete=False):
    coverage=inspect_coverage(windows=windows,required_start=required_start,required_end=required_end)
    evidence=assemble(session_snapshot=session_snapshot,intents=intents,
        positions=positions,observed_at=observed_at,
        broker_snapshot_complete=broker_snapshot_complete)
    if type(account_verified) is not bool or type(open_order_count) is not int or open_order_count<0:
        raise EvidenceBlocked("invalid_restart_inputs")
    restart=inspect_restart(account_verified=account_verified,
        position_count=len(positions),open_order_count=open_order_count,
        history_complete=False,attribution_certified=False)
    blockers=list(restart["blockers"])
    if not coverage["requested_window_covered"]:
        blockers.append("history_window_gap")
    if evidence["unattributed_positions"]:
        blockers.append("positions_unattributed")
    return {"status":"integrated_observation_only",
        "requested_window_covered":coverage["requested_window_covered"],
        "coverage_gap_detected":coverage["coverage_gap_detected"],
        "session_consistency_verified":evidence["session_consistency_verified"],
        "session_intent_count":evidence["session_intent_count"],
        "matched_fill_count":evidence["matched_fill_count"],
        "restart_clear":False,"blockers":blockers,
        "account_history_complete":False,"position_attribution_certified":False,
        "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
