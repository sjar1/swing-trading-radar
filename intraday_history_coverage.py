"""Conservative historical-window coverage checker; never certifies account lifetime."""
from datetime import datetime,timezone
from intraday_alpaca_fills import FillHistoryBlocked

def inspect_coverage(*,windows,required_start,required_end):
    if not isinstance(required_start,datetime) or not isinstance(required_end,datetime) or required_start.tzinfo is None or required_end.tzinfo is None:
        raise FillHistoryBlocked("invalid_coverage_bounds")
    start=required_start.astimezone(timezone.utc)
    end=required_end.astimezone(timezone.utc)
    if start>=end or not isinstance(windows,list) or len(windows)>1000:
        raise FillHistoryBlocked("invalid_coverage_request")
    intervals=[]
    for window in windows:
        if not isinstance(window,dict) or window.get("window_exhausted") is not True:
            raise FillHistoryBlocked("unverified_history_window")
        try:
            a=datetime.fromisoformat(window["window_start"].replace("Z","+00:00"))
            b=datetime.fromisoformat(window["window_end"].replace("Z","+00:00"))
        except (KeyError,AttributeError,TypeError,ValueError):
            raise FillHistoryBlocked("invalid_history_interval") from None
        if a.tzinfo is None or b.tzinfo is None or a>=b:
            raise FillHistoryBlocked("invalid_history_interval")
        intervals.append((a.astimezone(timezone.utc),b.astimezone(timezone.utc)))
    cursor=start
    for a,b in sorted(intervals):
        if a>cursor:break
        if b>cursor:cursor=b
        if cursor>=end:break
    covered=cursor>=end
    return {"requested_window_covered":covered,
            "coverage_gap_detected":not covered,
            "observed_window_count":len(intervals),
            "account_history_complete":False,"position_attribution_certified":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
