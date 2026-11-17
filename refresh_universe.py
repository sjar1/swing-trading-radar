"""Daily, rules-based universe rotation for PAPER-only Trading Radar.

Selects up to 30 liquid, volatile, relatively strong stocks from a transparent
curated candidate pool. Does not place orders. Falls back to previous verified
universe on data outages; never invents missing market data.
"""
import json, math, os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT=Path("docs/data/universe.json")
POOL=("GME AMC PLTR SOFI HOOD RKLB IONQ UPST LCID RIVN ACHR JOBY OPEN CHPT QS BLNK "
      "EVGO LYFT GRAB NU AFRM DKNG HIMS PATH AI SOUN BBAI CLSK MARA RIOT "
      "ASTS LUNR RGTI QBTS OKLO SMR NNE IREN CIFR HUT WULF BITF "
      "U SOUN RBLX SNAP PINS ROKU SHOP NET DDOG CRWD ZS CFLT "
      "CELH CAVA TOST DUOL APP CVNA WOLF ENVX MVST KULR "
      "FUBO CHWY NIO XPEV LI BILI PDD FUTU TIGR NCLH CCL "
      "AAL UAL DAL SAVE JBLU TGT PYPL SQ COIN MSTR").split()
MAX_SELECTED=30
def choose(data):
    ranked=[]
    for ticker,df in data.items():
        if df is None or len(df)<65:continue
        df=df.sort_index()
        close=pd.to_numeric(df["Close"],errors="coerce")
        high=pd.to_numeric(df["High"],errors="coerce")
        low=pd.to_numeric(df["Low"],errors="coerce")
        volume=pd.to_numeric(df["Volume"],errors="coerce")
        if any(x.tail(21).isna().any() for x in (close,high,low,volume)):continue
        price=float(close.iloc[-1])
        liquidity=float((close*volume).tail(20).mean())
        if not (2<=price<=25 and liquidity>=5_000_000):continue
        volatility=float(((high-low)/close.replace(0,float("nan"))).tail(20).mean())
        momentum=float(price/close.iloc[-21]-1)
        if not math.isfinite(volatility) or not math.isfinite(momentum):continue
        # Ranking is not a probability or order signal.
        score=round(100*(0.45*min(volatility/0.08,1)+
                         0.35*max(0,min((momentum+0.10)/0.30,1))+
                         0.20*min(liquidity/50_000_000,1)),2)
        ranked.append({"ticker":ticker,"price":round(price,2),
          "avg_dollar_volume_20d":round(liquidity),
          "avg_intraday_range_pct_20d":round(volatility*100,2),
          "return_20d_pct":round(momentum*100,2),"rank_score":score})
    return sorted(ranked,key=lambda x:(-x["rank_score"],x["ticker"]))[:MAX_SELECTED]
def main():
    previous=None
    if OUT.exists():
        try:previous=json.loads(OUT.read_text())
        except (ValueError,OSError):pass
    data={};errors=[]
    for ticker in dict.fromkeys(POOL):
        try:
            df=yf.download(ticker,period="6mo",interval="1d",auto_adjust=True,progress=False,threads=False)
            if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
            if df.empty:raise ValueError("empty history")
            # Drop current unfinished session to avoid ranking from partial data.
            if df.index[-1].date()>=datetime.now(timezone.utc).date():df=df.iloc[:-1]
            data[ticker]=df
        except Exception as exc:errors.append(ticker+": "+type(exc).__name__)
    selected=choose(data)
    # Prevent a transient provider outage from shrinking the universe.
    if len(selected)<15:
        if previous and len(previous.get("tickers",[]))>=15:
            print("Insufficient validated market data; retaining prior universe")
            return
        raise RuntimeError("Only "+str(len(selected))+" candidates validated; refusing universe rotation")
    result={"generated_at":datetime.now(timezone.utc).isoformat(),
      "selection_method":"Curated candidate pool; price $2-$25, 20d dollar volume >=$5m, 20d range/return/liquidity ranking",
      "tickers":[x["ticker"] for x in selected],"candidates":selected,
      "pool_size":len(set(POOL)),"errors":errors}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2)+"\n")
    print("Universe refreshed:",len(selected),"of",len(set(POOL)),"candidates;",len(errors),"data errors")
if __name__=="__main__":main()
