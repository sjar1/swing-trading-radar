"""Read-only, fail-closed fill-to-position attribution for intraday PAPER.

Uses an explicitly complete broker fill ledger, not current orders alone.
No broker writes; proof is informational, not execution authorization.
"""
from collections import defaultdict
from decimal import Decimal,InvalidOperation

class AttributionBlocked(RuntimeError):
    pass

def quantity(value):
    try:
        n=Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError):
        raise AttributionBlocked("invalid_quantity")
    if not n.is_finite() or n<=0:
        raise AttributionBlocked("invalid_quantity")
    return n

def attribute_positions(positions, fills, intents, *, fills_complete=False, dedicated_account=False):
    if not fills_complete or not dedicated_account:
        raise AttributionBlocked("unverified_broker_history_or_account")
    if not all(isinstance(x,list) for x in (positions,fills,intents)):
        raise AttributionBlocked("invalid_snapshot")
    ids={}
    for i in intents:
        if not isinstance(i,dict) or not isinstance(i.get("client_order_id"),str) or not i["client_order_id"].startswith("intraday-") or not isinstance(i.get("symbol"),str):
            raise AttributionBlocked("invalid_intent")
        if i["client_order_id"] in ids:
            raise AttributionBlocked("duplicate_intent")
        ids[i["client_order_id"]]=i["symbol"]
    balances=defaultdict(Decimal)
    seen=set()
    for f in fills:
        if not isinstance(f,dict) or not isinstance(f.get("event_id"),str) or not f["event_id"]:
            raise AttributionBlocked("incomplete_fill")
        if f["event_id"] in seen:
            raise AttributionBlocked("duplicate_fill")
        seen.add(f["event_id"])
        client=f.get("client_order_id")
        symbol=f.get("symbol")
        side=f.get("side")
        if client not in ids or ids[client]!=symbol or side not in ("buy","sell"):
            raise AttributionBlocked("unowned_or_invalid_fill")
        q=quantity(f.get("qty"))
        balances[symbol]+=q if side=="buy" else -q
        if balances[symbol]<0:
            raise AttributionBlocked("short_or_out_of_order_fill")
    observed={}
    for p in positions:
        if not isinstance(p,dict) or not isinstance(p.get("symbol"),str) or p.get("side")!="long":
            raise AttributionBlocked("invalid_or_short_position")
        symbol=p["symbol"]
        if symbol in observed:
            raise AttributionBlocked("duplicate_position")
        observed[symbol]=quantity(p.get("qty"))
    expected={k:v for k,v in balances.items() if v!=0}
    if expected!=observed:
        raise AttributionBlocked("broker_position_fill_mismatch")
    return {"verified":True,"positions":{k:str(v) for k,v in observed.items()},
            "broker_writes":0,"execution_enabled":False}
