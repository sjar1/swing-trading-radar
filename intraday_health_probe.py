"""One-shot read-only intraday PAPER health probe.

Not a continuous watchdog or permission to execute. No broker/DB writes.
"""
import json
import os
import sys
from datetime import datetime,timezone
from intraday_monitor_health import evaluate_health,REQUIRED

def probe(*,api_fn=None,connect_fn=None,now_fn=None,reconciliation_evidence=None):
    if api_fn is None:
        from intraday_engine import api as api_fn
    if connect_fn is None:
        import psycopg
        connect_fn=psycopg.connect
    if now_fn is None:
        now_fn=lambda:datetime.now(timezone.utc)
    now=now_fn()
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise ValueError("invalid_probe_clock")
    stamp=now.astimezone(timezone.utc).isoformat()
    heartbeats={name:{"healthy":False,"observed_at":stamp} for name in REQUIRED}
    problems=[]
    account=None
    try:
        from intraday_engine import PAPER
        account=api_fn(PAPER,"/v2/account")
        if not isinstance(account,dict) or account.get("status")!="ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
            raise ValueError("paper_account_not_ready")
        heartbeats["broker"]["healthy"]=True
    except Exception:
        problems.append("broker_unavailable")
    try:
        from intraday_engine import PAPER
        clock=api_fn(PAPER,"/v2/clock")
        if not isinstance(clock,dict) or not isinstance(clock.get("is_open"),bool) or not isinstance(clock.get("timestamp"),str):
            raise ValueError("invalid_clock")
        heartbeats["clock"]["healthy"]=True
    except Exception:
        problems.append("clock_unavailable")
    try:
        url=os.environ["INTRADAY_DATABASE_URL"]
        with connect_fn(url,connect_timeout=8,sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT 1 FROM intraday_paper.sessions LIMIT 1")
                cur.fetchall()
        heartbeats["database"]["healthy"]=True
    except Exception:
        problems.append("database_unavailable")
    try:
        from intraday_engine import PAPER
        from intraday_risk_snapshot import assess
        if account is None:
            raise ValueError("account_missing")
        positions=api_fn(PAPER,"/v2/positions")
        orders=api_fn(PAPER,"/v2/orders?status=open&limit=500")
        if not isinstance(positions,list) or not isinstance(orders,list) or len(positions)>=500 or len(orders)>=500:
            raise ValueError("risk_snapshot_incomplete")
        risk=assess(account,positions,orders)
        if not risk["within_limits"]:
            raise ValueError("risk_limit_reached")
        heartbeats["risk"]["healthy"]=True
    except Exception:
        problems.append("risk_unverified_or_limit_reached")
    # These components require independent runtime evidence; do not manufacture
    # green heartbeats based on a successful broker or database connection.
    try:
        from intraday_reconciliation_health import evaluate as evaluate_reconciliation
        evaluate_reconciliation(reconciliation_evidence,now=now)
        heartbeats["reconciliation"]["healthy"]=True
    except Exception:
        problems.append("reconciliation_not_verified")
    result=evaluate_health(heartbeats,now)
    return {"mode":"PAPER_READ_ONLY","status":"blocked","observed_components":
            sorted(k for k,v in heartbeats.items() if v["healthy"]),
            "problems":sorted(set(problems+result["problems"])),
            "monitor_fully_healthy":result["healthy"],
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}

def main():
    try:
        print(json.dumps(probe(),sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"mode":"PAPER_READ_ONLY","status":"blocked",
                          "reason":type(exc).__name__,"execution_enabled":False,
                          "broker_writes":0},sort_keys=True))
        return 3

if __name__=="__main__":
    sys.exit(main())
