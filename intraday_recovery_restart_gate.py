"""Fail-closed recovery restart gate using fresh independently verified broker data.

A passing check permits only further simulation, never order execution.
"""
from datetime import datetime,timezone
from intraday_recovery_checkpoint_db import validate_checkpoint,CheckpointBlocked
from intraday_recovery_journal import advance,RecoveryJournalBlocked

class RestartBlocked(RuntimeError):
    pass

def restart_observation(payload,*,session_date,checkpoint_observed_at,now,broker_observation):
    try:
        prior=validate_checkpoint(payload,session_date=session_date,
            max_age_seconds=90,observed_at=checkpoint_observed_at,now=now)["state"]
        if not isinstance(broker_observation,dict):
            raise RestartBlocked("missing_broker_observation")
        observed=broker_observation.get("observed_at")
        if not isinstance(observed,str):
            raise RestartBlocked("missing_broker_timestamp")
        dt=datetime.fromisoformat(observed.replace("Z","+00:00"))
        if dt.tzinfo is None:
            raise RestartBlocked("naive_broker_timestamp")
        age=(now.astimezone(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()
        if age<0 or age>30:
            raise RestartBlocked("stale_broker_observation")
        # Require a NEW observation after the checkpoint; a replay cannot
        # prove the state still matches the broker following a restart.
        if dt<=checkpoint_observed_at:
            raise RestartBlocked("broker_snapshot_not_newer_than_checkpoint")
        next_state=advance(prior,broker_observation)
        return {"phase":next_state.phase,"reconciliation_required":True,
                "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
    except (CheckpointBlocked,RecoveryJournalBlocked,ValueError,TypeError,OverflowError) as exc:
        raise RestartBlocked("restart_not_verified") from None
