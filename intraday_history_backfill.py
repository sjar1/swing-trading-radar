"""Read-only bounded historical backfill with contiguous window verification.

An observed date range never establishes account inception or lifetime completeness.
"""
from datetime import datetime,timezone,timedelta
from intraday_account_history import collect_window
from intraday_history_coverage import inspect_coverage
from intraday_alpaca_fills import FillHistoryBlocked

def inspect_backfill(*,api_fn,base,start_utc,end_utc,window_hours=1,
                     max_windows=24,collect_fn=collect_window):
    if not callable(api_fn) or not callable(collect_fn):
        raise FillHistoryBlocked("invalid_backfill_dependencies")
    if not isinstance(start_utc,datetime) or not isinstance(end_utc,datetime) or start_utc.tzinfo is None or end_utc.tzinfo is None:
        raise FillHistoryBlocked("invalid_backfill_bounds")
    if type(window_hours) is not int or not 1<=window_hours<=24 or type(max_windows) is not int or not 1<=max_windows<=168:
        raise FillHistoryBlocked("invalid_backfill_limits")
    start=start_utc.astimezone(timezone.utc)
    end=end_utc.astimezone(timezone.utc)
    if start>=end or end>datetime.now(timezone.utc)+timedelta(minutes=5):
        raise FillHistoryBlocked("invalid_backfill_bounds")
    duration=timedelta(hours=window_hours)
    needed=(end-start+duration-timedelta(microseconds=1))//duration
    if needed>max_windows:
        raise FillHistoryBlocked("backfill_window_limit")
    windows=[]
    seen_events=set()
    cursor=start
    fill_count=0
    while cursor<end:
        stop=min(end,cursor+duration)
        snapshot=collect_fn(api_fn=api_fn,base=base,start_utc=cursor,end_utc=stop,
                            max_pages=20,clock_fn=lambda:datetime.now(timezone.utc))
        if not isinstance(snapshot,dict) or not isinstance(snapshot.get("fills"),list):
            raise FillHistoryBlocked("invalid_backfill_snapshot")
        if snapshot.get("window_start")!=cursor.isoformat() or snapshot.get("window_end")!=stop.isoformat():
            raise FillHistoryBlocked("backfill_window_mismatch")
        for fill in snapshot["fills"]:
            if not isinstance(fill,dict) or not isinstance(fill.get("event_id"),str) or not fill["event_id"]:
                raise FillHistoryBlocked("invalid_backfill_fill")
            if fill["event_id"] in seen_events:
                raise FillHistoryBlocked("duplicate_backfill_fill")
            seen_events.add(fill["event_id"])
            fill_count+=1
        windows.append(snapshot)
        cursor=stop
    coverage=inspect_coverage(windows=windows,required_start=start,required_end=end)
    if not coverage["requested_window_covered"]:
        raise FillHistoryBlocked("backfill_coverage_gap")
    return {"status":"bounded_history_observed","window_count":len(windows),
            "observed_fill_count":fill_count,"requested_window_covered":True,
            "account_history_complete":False,"position_attribution_certified":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
