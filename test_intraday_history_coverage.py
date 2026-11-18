import unittest
from datetime import datetime,timezone,timedelta
from intraday_history_coverage import inspect_coverage
from intraday_alpaca_fills import FillHistoryBlocked
T=datetime(2026,11,18,tzinfo=timezone.utc)
def window(a,b,exhausted=True):
    return {"window_start":(T+timedelta(hours=a)).isoformat(),
            "window_end":(T+timedelta(hours=b)).isoformat(),
            "window_exhausted":exhausted}
def check(windows):
    return inspect_coverage(windows=windows,required_start=T,required_end=T+timedelta(hours=3))
class HistoryCoverageTests(unittest.TestCase):
    def test_contiguous(self):
        x=check([window(1,3),window(0,1)])
        self.assertTrue(x["requested_window_covered"])
        self.assertFalse(x["account_history_complete"])
        self.assertFalse(x["execution_enabled"])
    def test_gap(self):
        self.assertTrue(check([window(0,1),window(2,3)])["coverage_gap_detected"])
    def test_no_windows(self):
        self.assertTrue(check([])["coverage_gap_detected"])
    def test_overlap(self):
        self.assertTrue(check([window(0,2),window(1,3)])["requested_window_covered"])
    def test_unverified_window(self):
        with self.assertRaises(FillHistoryBlocked):check([window(0,3,False)])
    def test_bad_timestamp(self):
        with self.assertRaises(FillHistoryBlocked):
            check([{"window_start":"bad","window_end":"bad","window_exhausted":True}])
    def test_invalid_bounds(self):
        with self.assertRaises(FillHistoryBlocked):
            inspect_coverage(windows=[],required_start=T,required_end=T)
if __name__=="__main__":unittest.main()
