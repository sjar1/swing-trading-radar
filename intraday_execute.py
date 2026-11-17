"""Intraday momentum confirmation using Alpaca IEX daily bars only.

No order submissions here. Today's IEX volume is compared with full prior
IEX sessions, intentionally conservative (not projected). Indicators incorporate
today's partial daily bar. Missing/stale data fail closed.
"""
import json, os, math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import pandas as pd
from trading_radar import indicators, UNIVERSE

OUT=Path("docs/data/intraday_signals.json")
EASTERN=ZoneInfo("America/New_York")
BASE="https://data.alpaca.markets"
def api(path,params):
    query=urlencode(params)
    headers={"APCA-API-KEY-ID":os.environ["ALPACA_API_KEY"],
             "APCA-API-SECRET-KEY":os.environ["ALPACA_API_SECRET"]}
    with urlopen(Request(BASE+path+"?"+query,headers=headers),timeout=25) as resp:
        return json.load(resp)
def num(x):
    try:
        value=float(x)
        return value if math.isfinite(value) else None
    except (TypeError,ValueError):return None
def market_hours(now):
    local=now.astimezone(EASTERN)
    minute=local.hour*60+local.minute
    return local.weekday()<5 and 9*60+45<=minute<15*60+45
def evaluate_bars(ticker,bars,now):
    local_date=now.astimezone(EASTERN).date()
    records=[]
    for bar in bars:
        timestamp=datetime.fromisoformat(bar["t"].replace("Z","+00:00"))
        day=timestamp.astimezone(EASTERN).date()
        if day>local_date:continue
        records.append((day,bar))
    records.sort(key=lambda item:item[0])
    prior=[(d,b) for d,b in records if d<local_date]
    current=[b for d,b in records if d==local_date]
    if len(prior)<65 or len(current)!=1:return None
    today=current[0]
    if not all(num(today.get(k)) is not None for k in ("o","h","l","c","v")):return None
    price=num(today["c"]);volume=num(today["v"])
    if price is None or not 2<=price<=25 or volume<=0:return None
    avg_volume=sum(float(b["v"]) for _,b in prior[-20:])/20
    avg_dollar_volume=sum(float(b["c"])*float(b["v"]) for _,b in prior[-20:])/20
    if avg_volume<=0:return None
    rvol=volume/avg_volume
    prior_high=max(float(b["h"]) for _,b in prior[-20:])
    rows=prior[-100:]+[(local_date,today)]
    df=pd.DataFrame([{"Open":float(b["o"]),"High":float(b["h"]),
      "Low":float(b["l"]),"Close":float(b["c"]),"Volume":float(b["v"])}
      for _,b in rows],index=pd.DatetimeIndex([str(d) for d,_ in rows]))
    x=indicators(df).iloc[-1]
    trend=price>float(x.ema20) and price>float(x.ema50)
    momentum=(avg_dollar_volume>=5_000_000 and trend and price>prior_high and
              rvol>=2 and 55<=float(x.rsi)<=75 and float(x.macdh)>0)
    # Consistent with existing daily momentum scoring (25+20+15+5)/80.
    score=round(100*(25+20+15+5)/80) if momentum else 0
    stop=round(price-2*float(x.atr),2)
    qualified=bool(momentum and score>=75 and 0<stop<price)
    return {"ticker":ticker,"date":str(local_date),"price":round(price,2),
       "rvol":round(rvol,2),"rsi":round(float(x.rsi),1),
       "score":score,"strategy":"momentum" if qualified else "watch",
       "qualified":qualified,"stop_reference":stop if qualified else None,
       "prior_20d_high":round(prior_high,2),
       "data_source":"Alpaca IEX daily bars; partial current session",
       "volume_method":"Current IEX session volume / average 20 completed IEX sessions (unprojected)",
       "avg_iex_daily_dollar_volume":round(avg_dollar_volume,2)}
def main():
    now=datetime.now(timezone.utc)
    if not market_hours(now):
        print("Outside regular-session execution window; no intraday orders")
        return
    tickers=list(dict.fromkeys(t.strip().upper() for t in UNIVERSE if t.strip()))
    start=(now-timedelta(days=190)).date().isoformat()
    results=[];errors=[]
    snapshots=api("/v2/stocks/snapshots",{"symbols":",".join(tickers),"feed":"iex"}).get("snapshots",{})
    for ticker in tickers:
        try:
            payload=api("/v2/stocks/"+ticker+"/bars",{"timeframe":"1Day","start":start,
                "end":now.isoformat(),"limit":250,"feed":"iex","adjustment":"raw"})
            bars=payload.get("bars") or []
            snapshot=snapshots.get(ticker) or {}
            daily=snapshot.get("dailyBar") or {}
            trade=snapshot.get("latestTrade") or {}
            # The snapshot supplies the current partial session, while historical
            # daily bars supply only completed sessions.
            current_date=now.astimezone(EASTERN).date()
            latest_price=num(trade.get("p"))
            if not daily or latest_price is None or latest_price<=0:continue
            ts=trade.get("t")
            if not ts:continue
            trade_time=datetime.fromisoformat(ts.replace("Z","+00:00"))
            if (now-trade_time).total_seconds()>300 or (now-trade_time).total_seconds()<0:continue
            if trade_time.astimezone(EASTERN).date()!=current_date:continue
            current_bar={"t":now.isoformat(),"o":daily.get("o"),"h":daily.get("h"),
               "l":daily.get("l"),"c":latest_price,"v":daily.get("v")}
            bars=[b for b in bars if datetime.fromisoformat(b["t"].replace("Z","+00:00")).astimezone(EASTERN).date()<current_date]
            bars.append(current_bar)
            if payload.get("next_page_token"):
                errors.append(ticker+": historical bars paginated; skipped")
                continue
            item=evaluate_bars(ticker,bars,now)
            if item:results.append(item)
        except Exception as exc:
            errors.append(ticker+": "+type(exc).__name__)
    if not results:
        raise RuntimeError("No valid intraday IEX bars; no orders")
    payload={"generated_at":now.isoformat(),"mode":"intraday_iex",
      "signals":sorted(results,key=lambda s:s["score"],reverse=True),
      "errors":errors,"execution_note":"Conservative unprojected IEX volume; 15-minute schedule is not streaming."}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2)+"\n")
    print("Intraday confirmations:",sum(s["qualified"] for s in results),"of",len(results))
if __name__=="__main__":main()
