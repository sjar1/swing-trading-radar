"""Deterministic cancel-first recovery simulator. Never calls broker APIs.

A plan is not authorization. Reconcile each snapshot before advancing.
"""
from dataclasses import dataclass,field

class RecoveryBlocked(RuntimeError):
    pass

@dataclass
class Recovery:
    phase:str="observe"
    expected_order_ids:set=field(default_factory=set)
    expected_positions:dict=field(default_factory=dict)
    events:list=field(default_factory=list)

    def plan(self,open_order_ids,positions,*,snapshot_complete=False,ownership_verified=False):
        if self.phase!="observe":
            raise RecoveryBlocked("plan_already_started")
        if not snapshot_complete or not ownership_verified:
            raise RecoveryBlocked("snapshot_or_ownership_unverified")
        if not isinstance(open_order_ids,list) or len(set(open_order_ids))!=len(open_order_ids) or any(not isinstance(x,str) or not x for x in open_order_ids):
            raise RecoveryBlocked("invalid_orders")
        if not isinstance(positions,dict) or any(not isinstance(s,str) or not s or type(q)!=int or q<=0 for s,q in positions.items()):
            raise RecoveryBlocked("invalid_positions")
        self.expected_order_ids=set(open_order_ids)
        self.expected_positions=dict(positions)
        self.phase="await_cancel_ack" if open_order_ids else "ready_to_close"
        self.events.append("cancel_first_plan")
        return {"would_cancel":sorted(self.expected_order_ids),"would_close":{},
                "broker_writes":0,"execution_enabled":False}

    def observe_cancellations(self,remaining_order_ids,*,snapshot_complete=False):
        if self.phase!="await_cancel_ack":
            raise RecoveryBlocked("unexpected_cancel_observation")
        if not snapshot_complete or not isinstance(remaining_order_ids,list) or any(not isinstance(x,str) for x in remaining_order_ids):
            raise RecoveryBlocked("incomplete_cancel_observation")
        if remaining_order_ids:
            self.events.append("cancellation_unconfirmed")
            raise RecoveryBlocked("open_orders_remain")
        self.phase="ready_to_close"
        self.events.append("cancellation_confirmed")

    def close_plan(self,positions,*,snapshot_complete=False,ownership_verified=False):
        if self.phase!="ready_to_close":
            raise RecoveryBlocked("cancel_ack_required")
        if not snapshot_complete or not ownership_verified or not isinstance(positions,dict):
            raise RecoveryBlocked("position_snapshot_unverified")
        if positions!=self.expected_positions:
            raise RecoveryBlocked("position_changed_during_cancel")
        self.phase="await_flat_ack" if positions else "flat"
        self.events.append("close_plan_only")
        return {"would_close":dict(positions),"broker_writes":0,"execution_enabled":False}

    def observe_flat(self,positions,open_order_ids,*,snapshot_complete=False):
        if self.phase!="await_flat_ack":
            raise RecoveryBlocked("unexpected_flat_observation")
        if not snapshot_complete or not isinstance(positions,dict) or not isinstance(open_order_ids,list):
            raise RecoveryBlocked("incomplete_flat_observation")
        if positions or open_order_ids:
            self.events.append("flat_not_confirmed")
            raise RecoveryBlocked("not_flat")
        self.phase="flat"
        self.events.append("flat_confirmed")
        return {"flat":True,"broker_writes":0,"execution_enabled":False}
