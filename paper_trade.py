"""Local simulated paper ledger. No brokerage access or real orders."""
import json
from datetime import datetime, timezone
from pathlib import Path

DATA=Path("docs/data")
LEDGER=DATA/"paper_account.json"
START=5000.0
def run():
    signals=json.loads((DATA/"signals.json").read_text())
    day=signals["generated_at"][:10]
    if LEDGER.exists():
        state=json.loads(LEDGER.read_text())
    else:
        state={"starting_cash":START,"cash":START,"positions":{},"pending":[],"trades":[],"equity_history":[],"last_processed_date":None}
    if state["last_processed_date"]==day:
        print("Paper ledger already processed this UTC day")
        return
    prices={x["ticker"]:x for x in signals.get("signals",[]) if isinstance(x.get("price"),(int,float)) and x["price"]>0}
    # Execute prior day's pending decisions at the next observed close.
    for order in state["pending"]:
        t=order["ticker"]
        if t not in prices or t in state["positions"]:continue
        price=float(prices[t]["price"])
        stop=float(order["stop"])
        if price<=stop:continue
        qty=max(0,int(min(state["cash"]*.25/price, state["cash"]/price, state["starting_cash"]*.01/(price-stop))))
        if qty<1:continue
        state["cash"]=round(state["cash"]-qty*price,2)
        state["positions"][t]={"shares":qty,"entry":price,"stop":stop,"target":round(price+3*(price-stop),2),"opened":day,"last_price":price}
        state["trades"].append({"date":day,"ticker":t,"action":"BUY","shares":qty,"price":price,"note":"Next observed daily close; simulated"})
    state["pending"]=[]
    for t,pos in list(state["positions"].items()):
        if t not in prices:continue
        price=float(prices[t]["price"])
        pos["last_price"]=price
        reason="stop" if price<=pos["stop"] else "target" if price>=pos["target"] else None
        # Never exit a position on its entry day.
        if reason and pos["opened"]!=day:
            state["cash"]=round(state["cash"]+pos["shares"]*price,2)
            state["trades"].append({"date":day,"ticker":t,"action":"SELL","shares":pos["shares"],"price":price,"pnl":round(pos["shares"]*(price-pos["entry"]),2),"note":reason+" at observed close; simulated, not stop execution"})
            del state["positions"][t]
    for x in signals.get("signals",[]):
        if not x.get("qualified") or x.get("strategy")!="momentum" or x["ticker"] in state["positions"]:continue
        if any(o["ticker"]==x["ticker"] for o in state["pending"]):continue
        stop=x.get("stop_reference")
        if isinstance(stop,(int,float)) and 0<=stop<x["price"]:
            state["pending"].append({"ticker":x["ticker"],"stop":stop,"signal_date":day})
    equity=round(state["cash"]+sum(p["shares"]*p["last_price"] for p in state["positions"].values()),2)
    state["equity_history"].append({"date":day,"equity":equity,"cash":state["cash"]})
    state["equity_history"]=state["equity_history"][-365:]
    state["last_processed_date"]=day
    state["updated_at"]=datetime.now(timezone.utc).isoformat()
    DATA.mkdir(parents=True,exist_ok=True)
    LEDGER.write_text(json.dumps(state,indent=2)+"\n")
    print("Paper ledger:",len(state["positions"]),"positions, equity",equity)
if __name__=="__main__":run()
