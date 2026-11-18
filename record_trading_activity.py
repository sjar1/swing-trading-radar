"""Publish bounded, credential-free Trading Radar scan and order activity history."""
import json
from pathlib import Path
from datetime import datetime,timezone
p=Path("docs/data")
def read(name,default):
    try:return json.loads((p/name).read_text())
    except (OSError,ValueError):return default
signals=read("intraday_signals.json",{})
paper=read("alpaca_paper.json",{})
history=read("trading_activity.json",[])
if not isinstance(history,list):history=[]
rows=signals.get("signals",[])
qualified=[x.get("ticker") for x in rows if x.get("qualified")]
rejected=sorted((x for x in rows if not x.get("qualified")),key=lambda x:(len(x.get("rejection_reasons",[])),abs(float(x.get("rvol",0))-1.2)))[:10]
orders=paper.get("orders_submitted_this_run",[]) if paper.get("scan_type")=="intraday" else []
entry={"timestamp":signals.get("generated_at",datetime.now(timezone.utc).isoformat()),
       "evaluated":len(rows),"qualified":qualified,
       "closest":[{"ticker":x.get("ticker"),"price":x.get("price"),"rvol":x.get("rvol"),
                   "failed":x.get("rejection_reasons",[])} for x in rejected],
       "orders_submitted":orders,
       "reason":"No stocks passed all entry filters" if not qualified else
                ("Qualified stocks found; check execution and risk controls" if not orders else "Paper orders submitted")}
if not history or history[-1].get("timestamp")!=entry["timestamp"]:
    history.append(entry)
(p/"trading_activity.json").write_text(json.dumps(history[-500:],indent=2)+"\n")
print("Activity recorded:",entry["evaluated"],"evaluated,",len(qualified),"qualified,",len(orders),"orders in latest paper snapshot")
