"""Immutable, restart-safe recovery observation reducer (simulation only).

No broker access, persistence, or execution. Replayed observations are idempotent,
but contradictory or incomplete snapshots stop recovery.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

class RecoveryJournalBlocked(RuntimeError):
    pass

@dataclass(frozen=True)
class RecoveryJournal:
    phase:str="await_cancel_ack"
    last_sequence:int=0
    last_digest:str=""
    cancellation_confirmed:bool=False
    flat_confirmed:bool=False

def digest(snapshot):
    return sha256(json.dumps(snapshot,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def advance(state,observation):
    if not isinstance(state,RecoveryJournal) or not isinstance(observation,dict):
        raise RecoveryJournalBlocked("invalid_observation")
    seq=observation.get("sequence")
    if type(seq)!=int or seq<1:
        raise RecoveryJournalBlocked("invalid_sequence")
    try:
        fingerprint=digest(observation)
    except (TypeError,ValueError):
        raise RecoveryJournalBlocked("invalid_snapshot")
    if seq==state.last_sequence:
        if fingerprint==state.last_digest:
            return state
        raise RecoveryJournalBlocked("conflicting_replay")
    if seq!=state.last_sequence+1:
        raise RecoveryJournalBlocked("missing_observation")
    if observation.get("snapshot_complete") is not True or observation.get("ownership_verified") is not True:
        raise RecoveryJournalBlocked("unverified_snapshot")
    orders=observation.get("open_order_ids")
    positions=observation.get("positions")
    if not isinstance(orders,list) or any(not isinstance(x,str) or not x for x in orders) or len(orders)!=len(set(orders)):
        raise RecoveryJournalBlocked("invalid_orders")
    if not isinstance(positions,dict) or any(not isinstance(k,str) or not k or type(v)!=int or v<=0 for k,v in positions.items()):
        raise RecoveryJournalBlocked("invalid_positions")
    if state.phase=="await_cancel_ack":
        phase="await_cancel_ack" if orders else ("await_flat_ack" if positions else "flat")
    elif state.phase=="await_flat_ack":
        if orders:
            raise RecoveryJournalBlocked("orders_reappeared")
        phase="await_flat_ack" if positions else "flat"
    elif state.phase=="flat":
        if orders or positions:
            raise RecoveryJournalBlocked("flat_state_regressed")
        phase="flat"
    else:
        raise RecoveryJournalBlocked("unknown_phase")
    return RecoveryJournal(phase=phase,last_sequence=seq,last_digest=fingerprint,
                           cancellation_confirmed=phase!="await_cancel_ack",
                           flat_confirmed=phase=="flat")

def checkpoint(state):
    if not isinstance(state,RecoveryJournal):
        raise RecoveryJournalBlocked("invalid_state")
    return {"phase":state.phase,"last_sequence":state.last_sequence,
            "last_digest":state.last_digest,
            "cancellation_confirmed":state.cancellation_confirmed,
            "flat_confirmed":state.flat_confirmed,
            "execution_enabled":False,"broker_writes":0}

def restore(payload):
    if not isinstance(payload,dict):
        raise RecoveryJournalBlocked("invalid_checkpoint")
    try:
        state=RecoveryJournal(phase=payload["phase"],last_sequence=payload["last_sequence"],
            last_digest=payload["last_digest"],
            cancellation_confirmed=payload["cancellation_confirmed"],
            flat_confirmed=payload["flat_confirmed"])
    except (KeyError,TypeError):
        raise RecoveryJournalBlocked("invalid_checkpoint")
    if state.phase not in ("await_cancel_ack","await_flat_ack","flat") or type(state.last_sequence)!=int or state.last_sequence<0 or type(state.last_digest)!=str or type(state.cancellation_confirmed)!=bool or type(state.flat_confirmed)!=bool:
        raise RecoveryJournalBlocked("invalid_checkpoint")
    if state.cancellation_confirmed!=(state.phase!="await_cancel_ack") or state.flat_confirmed!=(state.phase=="flat") or (state.last_sequence==0 and state.last_digest!="") or (state.last_sequence>0 and len(state.last_digest)!=64):
        raise RecoveryJournalBlocked("inconsistent_checkpoint")
    return state
