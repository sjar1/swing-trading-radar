"""Fail-closed monitoring lease for the intraday PAPER pilot.

A passing health check is informational only: it never enables trading.
No broker or database writes.
"""
from datetime import datetime,timezone,timedelta

class MonitorBlocked(RuntimeError):
    pass

REQUIRED=("broker","reconciliation","database","risk","clock")

def parse_time(value):
    if not isinstance(value,str):
        raise MonitorBlocked("invalid_timestamp")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise MonitorBlocked("invalid_timestamp")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise MonitorBlocked("naive_timestamp")
    return dt.astimezone(timezone.utc)

def evaluate_health(heartbeats,now,*,max_age_seconds=90):
    if not isinstance(heartbeats,dict) or not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise MonitorBlocked("invalid_health_snapshot")
    if not isinstance(max_age_seconds,int) or isinstance(max_age_seconds,bool) or not 1<=max_age_seconds<=300:
        raise MonitorBlocked("invalid_age_limit")
    current=now.astimezone(timezone.utc)
    problems=[]
    for name in REQUIRED:
        item=heartbeats.get(name)
        if not isinstance(item,dict):
            problems.append(name+":missing")
            continue
        if item.get("healthy") is not True:
            problems.append(name+":unhealthy")
            continue
        try:
            seen=parse_time(item.get("observed_at"))
        except MonitorBlocked:
            problems.append(name+":invalid_timestamp")
            continue
        age=(current-seen).total_seconds()
        if age<0 or age>max_age_seconds:
            problems.append(name+":stale_or_future")
    return {"healthy":not problems,"problems":problems,
            "entry_permitted":False,"execution_enabled":False,
            "broker_writes":0,"monitor_max_age_seconds":max_age_seconds}

def require_monitor_health(heartbeats,now,*,max_age_seconds=90):
    status=evaluate_health(heartbeats,now,max_age_seconds=max_age_seconds)
    if not status["healthy"]:
        raise MonitorBlocked("monitor_unhealthy")
    return status
