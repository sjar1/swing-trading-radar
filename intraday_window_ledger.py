"""Conservative multi-window fill ledger verifier.

All windows must be contiguous and individually exhausted. This establishes
coverage only of the supplied interval, not lifetime account completeness.
"""
from datetime import datetime,timezone

class WindowLedgerBlocked(RuntimeError):
    pass

def parse(value):
    if not isinstance(value,str):
        raise WindowLedgerBlocked("invalid_timestamp")
    try: dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError: raise WindowLedgerBlocked("invalid_timestamp") from None
    if dt.tzinfo is None: raise WindowLedgerBlocked("naive_timestamp")
    return dt.astimezone(timezone.utc)

def merge_windows(windows):
    if not isinstance(windows,list) or not windows:
        raise WindowLedgerBlocked("missing_windows")
    merged=[]
    ids=set()
    previous_end=None
    for window in windows:
        if not isinstance(window,dict) or window.get("window_exhausted") is not True:
            raise WindowLedgerBlocked("window_not_exhausted")
        start=parse(window.get("window_start"))
        end=parse(window.get("window_end"))
        if start>=end or (previous_end is not None and start!=previous_end):
            raise WindowLedgerBlocked("gap_or_overlap")
        fills=window.get("fills")
        if not isinstance(fills,list) or type(window.get("activity_count"))!=int or window["activity_count"]!=len(fills):
            raise WindowLedgerBlocked("invalid_activity_count")
        for fill in fills:
            if not isinstance(fill,dict) or not isinstance(fill.get("event_id"),str) or not fill["event_id"]:
                raise WindowLedgerBlocked("invalid_fill")
            if fill["event_id"] in ids:
                raise WindowLedgerBlocked("duplicate_cross_window_fill")
            ids.add(fill["event_id"])
            # Window bounds must match the broker transaction timestamp.
            timestamp=parse(fill.get("transaction_time"))
            if timestamp<start or timestamp>=end:
                raise WindowLedgerBlocked("fill_outside_window")
            merged.append(fill)
        previous_end=end
    return {"window_start":parse(windows[0]["window_start"]).isoformat(),
            "window_end":previous_end.isoformat(),"windows_verified":len(windows),
            "fills":merged,"fill_count":len(merged),"interval_exhausted":True,
            "account_history_complete":False,"position_attribution_certified":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
