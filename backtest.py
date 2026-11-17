"""Conservative daily-bar research backtest; next-open fills and gap-aware exits."""
import argparse, json
import pandas as pd
import yfinance as yf
from trading_radar import indicators, position

def simulate(df, initial=5000, fee_bps=15):
    d=indicators(df).dropna().copy()
    cash=float(initial); trades=[]; equity=[cash]; open_trade=None
    for i in range(1,len(d)):
        x=d.iloc[i]; prev=d.iloc[i-1]
        if open_trade:
            t=open_trade; days=i-t["index"]
            # At open, adverse gaps execute at the opening price, not at stop.
            if x.Open<=t["stop"]: exit_price=float(x.Open)
            elif x.Low<=t["stop"]: exit_price=t["stop"]
            elif x.High>=t["target"]: exit_price=t["target"]
            elif days>=15: exit_price=float(x.Close)
            else: exit_price=None
            if exit_price is not None:
                proceeds=t["shares"]*exit_price*(1-fee_bps/10000)
                cash+=proceeds
                trades.append({"entry_date":t["date"],"exit_date":str(d.index[i].date()),"pnl":round(proceeds-t["cost"],2)})
                open_trade=None
        if not open_trade and prev.Close>prev.ema20 and prev.Close>prev.ema50 and prev.Close>prev.high20 and prev.rvol>=2 and 55<=prev.rsi<=75 and prev.macdh>0:
            entry=float(x.Open)*(1+fee_bps/10000)
            if entry<=float(prev.Close)*1.01 and float(x.Open)<=float(prev.Close)*1.03:
                stop=entry-2*float(prev.atr); qty=position(entry,stop,cash)["shares"]
                cost=qty*entry
                if qty and cost<=cash:
                    cash-=cost
                    open_trade={"index":i,"date":str(d.index[i].date()),"shares":qty,"stop":stop,"target":entry+2*(entry-stop),"cost":cost}
        equity.append(cash+(open_trade["shares"]*float(x.Close) if open_trade else 0))
    peak=pd.Series(equity).cummax()
    drawdown=float(((pd.Series(equity)/peak)-1).min()) if equity else 0
    wins=[t for t in trades if t["pnl"]>0]; losses=[t for t in trades if t["pnl"]<0]
    return {"trades":len(trades),"win_rate":round(len(wins)/len(trades),3) if trades else None,
            "realized_pnl":round(sum(t["pnl"] for t in trades),2),"ending_equity_marked":round(equity[-1],2),
            "max_drawdown":round(drawdown,4),"profit_factor":round(sum(t["pnl"] for t in wins)/abs(sum(t["pnl"] for t in losses)),2) if losses else None,
            "limitations":"Momentum-only prototype; no survivorship-free universe, verified historical short interest, or partial exits. Not suitable for live deployment."}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--ticker",default="SOFI");p.add_argument("--start",default="2020-01-01");a=p.parse_args()
    df=yf.download(a.ticker,start=a.start,auto_adjust=True,progress=False)
    if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    print(json.dumps(simulate(df),indent=2))
