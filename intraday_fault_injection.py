"""Offline fault-injection tests for durable equity and crash recovery.

No database credentials, broker access, or trading permissions are required.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from intraday_equity_monitor import transition
from intraday_crash_recovery import recovery_plan

DATE="2026-11-18"
KEY="intraday-20261118-AAPL-abc"

def run_scenarios():
    scenarios=[]
    def add(name, ok, detail):
        scenarios.append({"name":name,"passed":bool(ok),"detail":detail})
    # Consecutive observations: peak must never decrease, even after recovery.
    session=(Decimal("5000"),Decimal("5000"),Decimal("5000"),Decimal("0"),False,0)
    a=transition(session, "5075","5000")
    b=transition((5000,a["peak"],a["last"],a["drawdown"],a["blocked"],a["revision"]),"5030","5000")
    add("Repeated equity observations",a["revision"]==1 and b["revision"]==2 and b["peak"]==5075,
        "High-water mark retained and revision advanced twice")
    c=transition((5000,b["peak"],b["last"],b["drawdown"],b["blocked"],b["revision"]),"4975","5000")
    d=transition((5000,c["peak"],c["last"],c["drawdown"],c["blocked"],c["revision"]),"5100","5000")
    add("Loss threshold and sticky block",c["drawdown"]>=100 and c["blocked"] and d["blocked"],
        "A $100 peak-to-trough loss blocks trading; recovery does not unblock")
    ledger={"version":1,"session_date":DATE,
            "entries":{KEY:{"state":"reserved","reserved_risk":25}}}
    missing=recovery_plan(ledger,DATE,[],[])
    add("Crash after intent reservation",missing["retry_submission"] is False and
        KEY in missing["ambiguous_keys"] and not missing["safe_to_trade"],
        "Missing broker acknowledgement never authorizes resubmission")
    broker=[{"id":"broker-1","client_order_id":KEY,"status":"accepted"}]
    seen=recovery_plan(ledger,DATE,broker,[])
    add("Crash after broker acknowledgement",not seen["retry_submission"] and
        KEY in seen["ambiguous_keys"] and not seen["execution_enabled"],
        "Broker order found but reserved intent remains ambiguous")
    unknown=recovery_plan({"version":1,"session_date":DATE,"entries":{}},DATE,broker,[])
    add("Untracked broker order",unknown["reason"]=="unrecorded_broker_orders" and
        not unknown["safe_to_trade"],"Unknown intraday broker order requires reconciliation")
    add("Positions prevent recovery",recovery_plan(ledger,DATE,broker,[{"symbol":"AAPL"}])["reason"]==
        "position_attribution_unverified","Position ownership must be established first")
    return {"mode":"OFFLINE_FAULT_INJECTION","generated_at":datetime.now(timezone.utc).isoformat(),
            "execution_enabled":False,"orders_submitted":0,
            "passed":sum(x["passed"] for x in scenarios),"total":len(scenarios),
            "scenarios":scenarios}

def main():
    result=run_scenarios()
    out=Path("docs/data/intraday_safety.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"passed":result["passed"],"total":result["total"],
                      "execution_enabled":False,"orders_submitted":0}))
    return 0 if result["passed"]==result["total"] else 3

if __name__=="__main__":
    raise SystemExit(main())
