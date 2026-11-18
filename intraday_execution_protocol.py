"""Deterministic PAPER execution/flatten protocol simulator.

No Alpaca network requests or database mutations. Tests the exact safety
ordering required of a future durable broker executor.
"""
from dataclasses import dataclass,field

class SafetyStop(RuntimeError):
    pass

@dataclass
class PilotState:
    client_id:str
    phase:str="reserved"
    broker_id:str|None=None
    position_qty:int=0
    pending_cancel:bool=False
    close_requested:bool=False
    events:list=field(default_factory=list)
    halted:bool=True

    def record(self, event, **details):
        self.events.append({"event":event,**details})

    def submit_attempt(self):
        if self.phase!="reserved":
            raise SafetyStop("duplicate_or_ambiguous_submission")
        self.phase="submission_unknown"
        self.record("submission_attempt_recorded_before_network")
        # Network submission deliberately not implemented.
        return {"would_submit":True,"broker_writes":0}

    def acknowledge(self, broker_id, client_id):
        if self.phase!="submission_unknown" or not broker_id or client_id!=self.client_id:
            raise SafetyStop("acknowledgement_mismatch")
        self.broker_id=broker_id
        self.phase="acknowledged"
        self.record("broker_acknowledged",broker_id=broker_id)

    def timeout(self):
        if self.phase!="submission_unknown":
            raise SafetyStop("unexpected_timeout")
        self.phase="needs_reconciliation"
        self.record("ambiguous_timeout")
        return {"retry_allowed":False}

    def fill(self, qty):
        if self.phase not in ("acknowledged","partially_filled","filled") or not isinstance(qty,int) or isinstance(qty,bool) or qty<=0:
            raise SafetyStop("invalid_fill")
        self.position_qty+=qty
        self.phase="filled"
        self.record("fill_observed",qty=qty)

    def flatten_plan(self, open_order_ids, position_attributed, broker_snapshot_complete):
        if not broker_snapshot_complete:
            raise SafetyStop("incomplete_broker_snapshot")
        if not isinstance(open_order_ids,list) or any(not isinstance(x,str) or not x for x in open_order_ids):
            raise SafetyStop("invalid_open_orders")
        if self.phase in ("submission_unknown","needs_reconciliation"):
            raise SafetyStop("ambiguous_submission_requires_reconciliation")
        if self.position_qty and not position_attributed:
            raise SafetyStop("unattributed_position")
        self.pending_cancel=bool(open_order_ids)
        self.record("flatten_plan",cancel_count=len(open_order_ids),position_qty=self.position_qty)
        return {"cancel_first":list(open_order_ids),"close_after_cancel_ack":self.position_qty,
                "broker_writes":0}

    def cancel_ack(self, remaining_open_orders):
        if not self.pending_cancel:
            raise SafetyStop("cancel_not_pending")
        if remaining_open_orders:
            raise SafetyStop("cancel_not_confirmed")
        self.pending_cancel=False
        self.record("cancellations_confirmed")

    def close_plan(self, remaining_open_orders, position_attributed):
        if self.pending_cancel or remaining_open_orders:
            raise SafetyStop("cannot_close_before_cancel_confirmation")
        if self.position_qty and not position_attributed:
            raise SafetyStop("unattributed_position")
        self.close_requested=self.position_qty>0
        self.record("close_plan",qty=self.position_qty)
        return {"close_qty":self.position_qty,"broker_writes":0}

    def close_ack(self, remaining_positions, remaining_open_orders):
        if remaining_positions or remaining_open_orders:
            raise SafetyStop("not_flat")
        if not self.close_requested:
            raise SafetyStop("close_not_requested")
        self.position_qty=0
        self.phase="closed"
        self.record("flat_confirmed")
        return {"flat":True,"broker_writes":0}
