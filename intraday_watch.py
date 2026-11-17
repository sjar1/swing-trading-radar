"""Read-only intraday watchlist using Alpaca IEX snapshots and daily indicator context.

This script NEVER submits orders. IEX data may omit non-IEX trades.
"""
import json, os, math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import pandas as pd
import yfinance as yf
from trading_radar import indicators, UNIVERSE

OUT=Path("docs/data/intraday.json")
def fetch_snapshots(tickers):
    query=urlencode({"symbols":",".join(tickers),"feed":"iex"})
    url="https://data.alpaca.markets/v2/stocks/snapshots?"+query
    headers={"APCA-API-KEY-ID":os.environ["ALPACA_API_KEY"],
             "APCA-API-SECRET-KEY":os.environ["ALPACA_API_SECRET"]}
    with urlopen(Request(url,headers=headers),timeout=25) as resp:
        payload=json.load(resp)
        # Alpaca multi-symbol snapshots are keyed directly by ticker.
        return payload.get("snapshots",payload)
def finite(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError):
        return None
def main():
    tickers=list(dict.fromkeys(t.strip().upper() for t in UNIVERSE if t.strip()))
    snapshots=fetch_snapshots(tickers)
    print("Alpaca IEX snapshots received:",len(snapshots),"for",len(tickers),"symbols")
    results=[]; errors=[]
    for ticker in tickers:
        try:
            df=yf.download(ticker,period="6mo",interval="1d",auto_adjust=True,progress=False)
            if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
            if len(df)<65:
                errors.append(ticker+": insufficient historical daily bars")
                continue
            # Use only prior completed sessions for breakout, RSI, EMA and MACD context.
            df=df.sort_index()
            today=datetime.now(timezone.utc).date()
            if df.index[-1].date()>=today:df=df.iloc[:-1]
            if len(df)<65:
                errors.append(ticker+": insufficient completed daily bars")
                continue
            d=indicators(df)
            x=d.iloc[-1]
            snap=snapshots.get(ticker) or {}
            trade=snap.get("latestTrade") or {}
            minute=snap.get("minuteBar") or {}
            daily=snap.get("dailyBar") or {}
            price=finite(trade.get("p")) or finite(minute.get("c")) or finite(daily.get("c"))
            if price is None or price<=0:
                errors.append(ticker+": missing IEX last trade, minute bar and daily bar price")
                continue
            high20=float(d.High.tail(20).max())
            ema20=float(x.ema20);ema50=float(x.ema50)
            rsi=float(x.rsi);macdh=float(x.macdh)
            gap=(high20-price)/high20*100 if high20>0 else None
            dollar_vol=float((d.Close*d.Volume).tail(20).mean())
            trend=price>ema20 and price>ema50
            breakout=price>high20
            near=gap is not None and -1<=gap<=3
            # IEX daily volume is not comparable with consolidated daily history;
            # display it separately, never use it as a qualification trigger.
            volume=finite(daily.get("v"))
            prior_rvol=finite(x.rvol)
            warning=bool(2<=price<=25 and dollar_vol>=5_000_000 and trend and near and
                         50<=rsi<=78 and macdh>0)
            score=sum([25 if trend else 0,25 if near else 0,20 if macdh>0 else 0,
                       15 if 50<=rsi<=78 else 0,15 if breakout else 0])
            results.append({"ticker":ticker,"price":round(price,2),
              "trade_timestamp":trade.get("t") or minute.get("t"),
              "previous_20d_high":round(high20,2),"gap_to_breakout_pct":round(gap,2),
              "ema20":round(ema20,2),"ema50":round(ema50,2),
              "rsi_previous_close":round(rsi,1),"macd_hist_previous_close":round(macdh,4),
              "iex_day_volume":int(volume) if volume is not None else None,
              "previous_close_rvol":round(prior_rvol,2) if prior_rvol is not None else None,
              "early_warning":warning,"breakout_above_prior_high":breakout,
              "readiness_score":score,
              "context_date":str(d.index[-1].date())})
        except Exception as exc:
            errors.append(ticker+": "+type(exc).__name__+": "+str(exc)[:160])
    if not results:
        raise RuntimeError("No intraday prices available; diagnostics: "+"; ".join(errors[:8]))
    results.sort(key=lambda x:(not x["early_warning"],-x["readiness_score"],abs(x["gap_to_breakout_pct"])))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(),
      "source":"Alpaca IEX snapshot prices; Yahoo completed-session daily indicators",
      "disclaimer":"IEX-only prices and volumes may differ from consolidated market data. RSI/MACD/EMA use prior daily close. Read-only early warnings, NOT buy signals or orders.",
      "items":results,"errors":errors},indent=2)+"\n")
    print("Saved intraday snapshot:",len(results),"tickers;",sum(x["early_warning"] for x in results),"early warnings")
if __name__=="__main__":main()
