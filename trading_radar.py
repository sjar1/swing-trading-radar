"""Signals-only trading radar. Research/paper trading, not investment advice."""
import argparse, json, math, os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import yfinance as yf

UNIVERSE = os.getenv("RADAR_TICKERS", "GME,AMC,PLTR,SOFI,HOOD,RKLB,IONQ,UPST,LCID,RIVN,ACHR,JOBY,OPEN,CHPT,QS,BLNK,EVGO,LYFT,GRAB,NU,AFRM,DKNG,HIMS,PATH,AI,SOUN,BBAI,CLSK,MARA,RIOT").split(",")
OUT = Path("docs/data")
def indicators(df):
    d=df.copy()
    c=d["Close"]; v=d["Volume"]
    for n in (10,20,50): d[f"ema{n}"]=c.ewm(span=n,adjust=False).mean()
    delta=c.diff(); up=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    down=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    d["rsi"]=100-100/(1+up/down.replace(0,1e-10))
    prev=c.shift()
    tr=pd.concat([(d.High-d.Low),(d.High-prev).abs(),(d.Low-prev).abs()],axis=1).max(axis=1)
    d["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    d["rvol"]=v/v.rolling(20).mean()
    d["high10"]=d.High.shift(1).rolling(10).max()
    d["high20"]=d.High.shift(1).rolling(20).max()
    macd=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    d["macdh"]=macd-macd.ewm(span=9,adjust=False).mean()
    return d

def position(entry, stop, equity=5000, risk_fraction=.01):
    if entry<=0 or stop<0 or stop>=entry: return {"shares":0,"risk":0}
    shares=max(0,math.floor(min(equity*risk_fraction/(entry-stop),equity*.25/entry)))
    return {"shares":shares,"cost":round(shares*entry,2),"risk":round(shares*(entry-stop),2),"target_2r":round(entry+2*(entry-stop),2)}

def evaluate(ticker, history, short_interest=None, days_to_cover=None, catalyst=False):
    d=indicators(history)
    if len(d)<65: return None
    x=d.iloc[-1]; price=float(x.Close); dollar_vol=float((d.Close*d.Volume).tail(20).mean())
    if not (2<=price<=25 and dollar_vol>=5_000_000): return None
    trend=price>x.ema20 and price>x.ema50
    momentum=trend and price>x.high20 and x.rvol>=2 and 55<=x.rsi<=75 and x.macdh>0
    squeeze=(price>x.ema20 and price>x.high10 and x.rvol>=3 and 60<=x.rsi<=80
             and short_interest is not None and short_interest>=.15
             and days_to_cover is not None and days_to_cover>=3)
    reversal=(price>x.ema20 and price>x.high10 and x.rvol>=1.5 and 45<=x.rsi<=65 and catalyst)
    modes=[("squeeze",squeeze,2.5),("reversal",reversal,1.75),("momentum",momentum,2)]
    selected=next(((name,mult) for name,ok,mult in modes if ok),None)
    # Transparent ranking heuristic; not a probability.
    volume_pts=0 if x.rvol<1.5 else 8 if x.rvol<2 else 14 if x.rvol<3 else 20
    raw={"trend":25 if trend else 8 if price>x.ema20 else 0,
         "volume":volume_pts,"short":20 if squeeze else 10 if short_interest is not None and short_interest>=.15 else 0,
         "breakout":15 if price>x.high20 else 10 if price>x.high10 else 0,
         "catalyst":15 if catalyst else 0,"market":5 if trend else 0}
    if selected and selected[0]!="squeeze":
        score=round(100*(sum(raw.values())-raw["short"])/80)
    else: score=sum(raw.values())
    score=min(100,score)
    result={"ticker":ticker,"date":str(d.index[-1].date()),"price":round(price,2),
            "rvol":round(float(x.rvol),2),"rsi":round(float(x.rsi),1),
            "score":score,"strategy":selected[0] if selected else "watch",
            "qualified":bool(selected and score>=75),
            "short_data_verified":short_interest is not None and days_to_cover is not None,
            "catalyst_verified":bool(catalyst)}
    if selected:
        stop=round(price-selected[1]*float(x.atr),2)
        result.update({"entry_limit":round(price*1.01,2),"stop_reference":stop,
                       "sizing_at_close":position(price,stop)})
    return result

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]; errors=[]
    for ticker in [t.strip().upper() for t in UNIVERSE if t.strip()]:
        try:
            df=yf.download(ticker,period="1y",auto_adjust=True,progress=False)
            if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
            if df.empty: continue
            item=evaluate(ticker,df)
            if item:
                results.append(item)

        except Exception as exc:
            errors.append(f"{ticker}: {exc}")
            print(f"{ticker}: {exc}")
    results.sort(key=lambda x:x["score"],reverse=True)
    if not results and errors:
        raise RuntimeError("All ticker downloads failed; preserving last good dashboard data: " + "; ".join(errors[:3]))
    payload={"generated_at":datetime.now(timezone.utc).isoformat(),"data_policy":"Unverified squeeze/catalyst metrics are never inferred. Scores are research heuristics, not win probabilities.","signals":results,"errors":errors}
    (OUT/"signals.json").write_text(json.dumps(payload,indent=2))
    history=OUT/"history.json"
    old=json.loads(history.read_text()) if history.exists() else []
    old.append({"date":payload["generated_at"][:10],"scores":{x["ticker"]:x["score"] for x in results}})
    # One snapshot per date; retain full history in git.
    bydate={x["date"]:x for x in old}
    history.write_text(json.dumps(list(bydate.values()),indent=2))
    print(f"Saved {len(results)} screened tickers")

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--run",action="store_true"); args=p.parse_args()
    run()
