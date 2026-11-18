"""Read-only reconciliation evidence assembler.

Session-only evidence cannot certify account history or position ownership.
Never fabricate missing proofs or enable trading.
"""
from datetime import datetime,timezone
from intraday_durable_fill_reconciliation import reconcile_session,DurableFillBlocked

class EvidenceBlocked(RuntimeError):
    pass

def assemble(*,session_snapshot,intents,positions,observed_at,broker_snapshot_complete=False):
    if not isinstance(observed_at,datetime) or observed_at.tzinfo is None:
        raise EvidenceBlocked("invalid_observation_time")
    if not isinstance(session_snapshot,dict) or session_snapshot.get("session_history_exhausted") is not True:
        raise EvidenceBlocked("session_history_incomplete")
    fills=session_snapshot.get("fills")
    if not isinstance(fills,list) or not isinstance(intents,list) or not isinstance(positions,list):
        raise EvidenceBlocked("invalid_inputs")
    if broker_snapshot_complete is not True:
        raise EvidenceBlocked("broker_snapshot_unverified")
    seen=set()
    for position in positions:
        if not isinstance(position,dict) or not isinstance(position.get("symbol"),str) or not position["symbol"]:
            raise EvidenceBlocked("invalid_position")
        if position["symbol"] in seen:
            raise EvidenceBlocked("duplicate_position")
        seen.add(position["symbol"])
    try:
        consistency=reconcile_session(intents,fills)
    except DurableFillBlocked:
        raise EvidenceBlocked("session_intents_or_fills_unverified") from None
    return {"observed_at":observed_at.astimezone(timezone.utc).isoformat(),
            "session_history_exhausted":True,
            "session_consistency_verified":consistency["session_consistency_verified"],
            "durable_intents_verified":True,
            "broker_snapshot_complete":True,
            "account_history_complete":False,
            "position_attribution_certified":False,
            "unmatched_fills":0,
            "unattributed_positions":len(positions),
            "session_intent_count":consistency["session_intent_count"],
            "matched_fill_count":consistency["matched_fill_count"],
            "status":"session_only_account_history_unverified",
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
