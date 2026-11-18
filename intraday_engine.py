"""Isolated intraday PAPER engine. Dry-run by default; never contacts live trading."""
import json, math, os, urllib.request
from datetime import datetime, timezone, time
from pathlib import Path
from zoneinfo import ZoneInfo

PAPER="https://paper-api.alpaca.markets"
DATA="https://data.alpaca.markets"
OUT=Path("docs/data/intraday_engine.json")
SYMBOLS=("SPY","QQQ","AAPL","MSFT","NVDA","AMD")
NY=ZoneInfo("America/New_York")
RISK=25.0
DAILY_LOSS=100.0
MAX_EXPOSURE=2000.0
MAX_POSITIONS=2
MAX_ENTRIES=5

def api(base,path,method="GET",payload=None):
    if base not in (PAPER,DATA) or not path.startswith("/") or "://" in path:
        raise ValueError("Invalid API endpoint")
    headers={"APCA-API-KEY-ID":os.environ["ALPACA_API_KEY"],
             "APCA-API-SECRET-KEY":os.environ["ALPACA_API_SECRET"]}
    data=None if payload is None else json.dumps(payload).encode()
    if data: headers["Content-Type"]="application/json"
    req=urllib.request.Request(base+path,headers=headers,data=data,method=method)
    with urllib.request.urlopen(req,timeout=15) as response:
        return json.loads(response.read())

def finite(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):
        return None

def evaluate(bars):
    """Use completed 1-minute bars only; first 15 minutes define opening range."""
    if len(bars)<22: return None,"insufficient_bars"
    rows=[]
    for b in bars:
        o,h,l,c,v=(finite(b.get(k)) for k in ("o","h","l","c","v"))
        if None in (o,h,l,c,v) or min(o,h,l,c)<=0 or v<0 or not l<=min(o,c)<=max(o,c)<=h:
            return None,"invalid_bars"
        rows.append((o,h,l,c,v))
    last=rows[-1]; price=last[3]
    if not 10<=price<=150: return None,"price_filter"
    if sum(r[4] for r in rows[-5:])<=0: return None,"no_volume"
    opening=max(r[1] for r in rows[:15])
    total_volume=sum(r[4] for r in rows)
    vwap=sum(((r[1]+r[2]+r[3])/3)*r[4] for r in rows)/total_volume if total_volume else 0
    prior_volume=sum(r[4] for r in rows[-21:-1])/20
    if prior_volume<=0 or last[4]<1.5*prior_volume: return None,"volume_filter"
    if price<=vwap: return None,"below_vwap"
    strategy=None
    if price>opening and rows[-2][3]<=opening:
        strategy="opening_range_breakout"
        stop=min(rows[-3][2],opening)
    elif rows[-2][3]<=vwap and price>vwap and price>rows[-6][3]:
        strategy="vwap_reclaim"
        stop=min(r[2] for r in rows[-5:])
    else: return None,"no_setup"
    if not 0<price-stop<=price*0.025: return None,"stop_distance"
    return {"strategy":strategy,"price":price,"stop":stop,"vwap":round(vwap,4)}, "qualified"

def plan(signal,equity,remaining_exposure):
    price=signal["price"]; stop=signal["stop"]
    # Conservative limit-entry buffer; size to the maximum permitted entry.
    limit=round(price*1.001,2)
    stop=round(stop,2)
    if limit<=stop or stop<=0: return None
    per_share=limit-stop
    qty=math.floor(min(RISK/per_share,remaining_exposure/limit, equity*0.20/limit))
    if qty<1: return None
    target=round(limit+3*per_share,2)
    return {"qty":qty,"limit_price":f"{limit:.2f}","stop_loss":{"stop_price":f"{stop:.2f}"},
            "take_profit":{"limit_price":f"{target:.2f}"}}

def gate(account,positions,orders,day_entries,now):
    if now.weekday()>4 or not time(9,45)<=now.time()<time(15,15): return "outside_entry_window"
    if account.get("status")!="ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"): return "account_blocked"
    equity=finite(account.get("equity")); last=finite(account.get("last_equity"))
    if equity is None or last is None or equity<=0: return "invalid_equity"
    if equity-last<=-DAILY_LOSS: return "daily_loss_limit"
    if len(positions)+len([o for o in orders if o.get("side")=="buy"])>=MAX_POSITIONS: return "position_limit"
    if day_entries>=MAX_ENTRIES: return "entry_limit"
    return None

def main():
    now=datetime.now(NY)
    result={"generated_at":datetime.now(timezone.utc).isoformat(),"mode":"PAPER_DRY_RUN",
            "signals":[],"diagnostics":[],"orders_submitted":0}
    try:
        if not all(os.getenv(k) for k in ("ALPACA_API_KEY","ALPACA_API_SECRET")):
            result["status"]="missing_paper_credentials"; return
        clock=api(PAPER,"/v2/clock")
        account=api(PAPER,"/v2/account")
        positions=api(PAPER,"/v2/positions")
        orders=api(PAPER,"/v2/orders?status=open&limit=500")
        # Include every entry submitted today, even if already closed.
        from urllib.parse import quote
        start=now.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).isoformat()
        history=api(PAPER,"/v2/orders?status=all&limit=500&after="+quote(start))
        day_entries=sum(1 for o in history if o.get("side")=="buy" and o.get("status") not in ("rejected","canceled","expired"))
        blocked=gate(account,positions,orders,day_entries,now)
        if not clock.get("is_open"): blocked="market_closed"
        result["status"]=blocked or "scanning"
        if blocked: return
        held={p["symbol"] for p in positions}|{o["symbol"] for o in orders}
        exposure=sum(abs(finite(p.get("market_value")) or 0) for p in positions)
        exposure+=sum((finite(o.get("qty")) or 0)*(finite(o.get("limit_price")) or 0)
                      for o in orders if o.get("side")=="buy")
        available=max(0,min(MAX_EXPOSURE-exposure,finite(account.get("cash")) or 0))
        # Data source: Alpaca IEX, 1-minute bars, session-only. Deliberately exclude
        # the current potentially incomplete bar and never infer missing bars.
        from urllib.parse import urlencode
        for symbol in SYMBOLS:
            if symbol in held:
                result["diagnostics"].append({"symbol":symbol,"reason":"already_held_or_pending"}); continue
            if day_entries>=MAX_ENTRIES or len(held)>=MAX_POSITIONS: break
            start_time=now.replace(hour=9,minute=30,second=0,microsecond=0).astimezone(timezone.utc)
            end_time=now.replace(second=0,microsecond=0).astimezone(timezone.utc)
            params=urlencode({"timeframe":"1Min","start":start_time.isoformat(),"end":end_time.isoformat(),"limit":400,"feed":"iex"})
            payload=api(DATA,"/v2/stocks/"+symbol+"/bars?"+params)
            bars=payload.get("bars",[])
            # Enforce continuity and current-session freshness; no gaps or stale signals.
            times=[datetime.fromisoformat(b["t"].replace("Z","+00:00")) for b in bars]
            if not times or len(times)<22 or (end_time-times[-1]).total_seconds()>180 or any(
                (b-a).total_seconds()!=60 for a,b in zip(times,times[1:])):
                result["diagnostics"].append({"symbol":symbol,"reason":"stale_or_gapped_bars"}); continue
            signal,reason=evaluate(bars)
            result["diagnostics"].append({"symbol":symbol,"reason":reason})
            if not signal: continue
            trade=plan(signal,finite(account.get("equity")),available)
            if not trade: continue
            result["signals"].append({"symbol":symbol,**signal,**trade})
            if os.getenv("INTRADAY_PAPER_ORDERS")!="1": continue
            # Explicit PAPER-only opt-in. Never use a live endpoint.
            payload={"symbol":symbol,"qty":str(trade["qty"]),"side":"buy","type":"limit",
                     "time_in_force":"day","limit_price":trade["limit_price"],
                     "order_class":"bracket","take_profit":trade["take_profit"],
                     "stop_loss":trade["stop_loss"],
                     "client_order_id":"intraday-"+now.strftime("%Y%m%d")+"-"+symbol+"-"+signal["strategy"][:4]}
            api(PAPER,"/v2/orders","POST",payload)
            result["orders_submitted"]+=1
            day_entries+=1;held.add(symbol);available-=trade["qty"]*float(trade["limit_price"])
        result["status"]="scanned"
        if os.getenv("INTRADAY_PAPER_ORDERS")=="1": result["mode"]="PAPER_ORDERS_ENABLED"
    except Exception as exc:
        # Never emit credentials or raw broker errors.
        result["status"]="error";result["error_type"]=type(exc).__name__
        raise
    finally:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(result,indent=2)+"\n")

if __name__=="__main__":
    main()
