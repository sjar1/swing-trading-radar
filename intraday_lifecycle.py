"""Read-only Alpaca PAPER order lifecycle and flattening planner.

Never submits/cancels orders. Existing swing positions must not be touched.
Only orders with an exact intraday client-order prefix identify ownership.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from intraday_engine import api, PAPER, finite

NY = ZoneInfo("America/New_York")
PREFIX = "intraday-"

def owned_orders(orders):
    """Return top-level orders belonging to this strategy, including bracket legs."""
    return [o for o in orders if str(o.get("client_order_id","")).startswith(PREFIX)]

def flatten_plan(positions, orders, now, next_close=None):
    """Generate a proposed liquidation plan; never execute it.

    Account-wide net positions may be shared by strategies. Ownership cannot be
    inferred safely from a tagged order alone, so do not propose position closes.
    """
    now=now.astimezone(timezone.utc)
    close=next_close.astimezone(timezone.utc) if next_close else None
    due=bool(close and timedelta(0)<=close-now<=timedelta(minutes=30))
    owned=owned_orders(orders)
    return {
        "close_approaching":due,
        "owned_open_order_ids":[o["id"] for o in owned if o.get("id")],
        "proposed_cancel_order_ids":[o["id"] for o in owned if due and o.get("id")],
        "proposed_close_positions":[],
        "requires_manual_reconciliation":bool(positions),
        "reason":"shared_account_position_ownership_not_provable" if positions else "no_positions",
        "execution_enabled":False,
    }

def account_risk(account, peak_equity=None, active_risk=0):
    """Conservative read-only account risk snapshot; unknown data blocks."""
    equity=finite(account.get("equity"))
    last=finite(account.get("last_equity"))
    cash=finite(account.get("cash"))
    peak=finite(peak_equity)
    if equity is None or last is None or cash is None or equity<=0:
        return {"blocked":True,"reason":"unknown_account_state"}
    if peak is None:
        # Cannot reconstruct the day's true intraday peak from a single snapshot.
        return {"blocked":True,"reason":"missing_durable_peak_equity"}
    loss=max(last,peak)-equity
    if loss>=100: return {"blocked":True,"reason":"daily_drawdown","drawdown":round(loss,2)}
    if active_risk>50: return {"blocked":True,"reason":"risk_budget"}
    return {"blocked":False,"drawdown":round(loss,2),"remaining_loss_budget":round(100-loss,2)}

def snapshot():
    """Read-only PAPER account, clock, positions and orders."""
    account=api(PAPER,"/v2/account")
    positions=api(PAPER,"/v2/positions")
    orders=api(PAPER,"/v2/orders?status=open&limit=500&nested=true")
    clock=api(PAPER,"/v2/clock")
    close=datetime.fromisoformat(clock["next_close"].replace("Z","+00:00")) if clock.get("next_close") else None
    plan=flatten_plan(positions,orders,datetime.now(timezone.utc),close)
    return {"mode":"PAPER_READ_ONLY","account_risk":account_risk(account),
            "lifecycle":plan,"market_open":bool(clock.get("is_open"))}

if __name__=="__main__":
    import json
    from pathlib import Path
    output=Path("docs/data/intraday_lifecycle.json")
    try: result=snapshot()
    except Exception as exc: result={"mode":"PAPER_READ_ONLY","error_type":type(exc).__name__,"status":"error"}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+"\n")
