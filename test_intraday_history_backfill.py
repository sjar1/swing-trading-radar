import unittest
from datetime import datetime,timezone,timedelta
from intraday_history_backfill import inspect_backfill
from intraday_alpaca_fills import FillHistoryBlocked
T=datetime(2026,11,17,12,tzinfo=timezone.utc)
def collect(**kw):
    return {"window_start":kw["start_utc"].isoformat(),
            "window_end":kw["end_utc"].isoformat(),
            "window_exhausted":True,"fills":[]}
def run(collect_fn=collect,**kwargs):
    return inspect_backfill(api_fn=lambda *a:[],base="PAPER",start_utc=T,
        end_utc=T+timedelta(hours=3),collect_fn=collect_fn,**kwargs)
class BackfillTests(unittest.TestCase):
    def test_three_contiguous_windows(self):
        x=run()
        self.assertEqual(x["window_count"],3)
        self.assertTrue(x["requested_window_covered"])
        self.assertFalse(x["account_history_complete"])
        self.assertFalse(x["execution_enabled"])
    def test_truncated_window_fails(self):
        def bad(**kw):return {**collect(**kw),"window_exhausted":False}
        with self.assertRaises(FillHistoryBlocked):run(collect_fn=bad)
    def test_wrong_window_fails(self):
        def bad(**kw):return {**collect(**kw),"window_end":T.isoformat()}
        with self.assertRaises(FillHistoryBlocked):run(collect_fn=bad)
    def test_duplicate_event_fails(self):
        def dup(**kw):return {**collect(**kw),"fills":[{"event_id":"same"}]}
        with self.assertRaises(FillHistoryBlocked):run(collect_fn=dup)
    def test_budget_blocks_before_network(self):
        def no_network(**kw):raise AssertionError("unexpected API request")
        with self.assertRaises(FillHistoryBlocked):run(collect_fn=no_network,max_windows=2)
    def test_invalid_limits(self):
        with self.assertRaises(FillHistoryBlocked):run(window_hours=True)
    def test_naive_bounds(self):
        with self.assertRaises(FillHistoryBlocked):
            inspect_backfill(api_fn=lambda *a:[],base="PAPER",
                start_utc=T.replace(tzinfo=None),end_utc=T,collect_fn=collect)
if __name__=="__main__":unittest.main()
