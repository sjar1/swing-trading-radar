import unittest
from datetime import datetime,timezone,timedelta
from intraday_account_history import collect_window
from intraday_alpaca_fills import FillHistoryBlocked
START=datetime(2026,11,17,14,tzinfo=timezone.utc)
END=datetime(2026,11,17,21,tzinfo=timezone.utc)
def collect(api,**kw):return collect_window(api_fn=api,base="PAPER",start_utc=START,end_utc=END,**kw)
class HistoryTests(unittest.TestCase):
    def test_empty_window_not_lifetime_proof(self):
        x=collect(lambda base,path:[])
        self.assertTrue(x["window_exhausted"])
        self.assertFalse(x["account_history_complete"])
        self.assertFalse(x["execution_enabled"])
    def test_orders_cap_rejected(self):
        with self.assertRaises(FillHistoryBlocked):collect(lambda base,path:[{}]*500 if "/v2/orders?" in path else [])
    def test_activity_cap_rejected(self):
        with self.assertRaises(FillHistoryBlocked):collect(lambda base,path:[] if "/v2/orders?" in path else [{"id":str(i)} for i in range(100)],max_pages=1)
    def test_unmatched_fill_rejected(self):
        def api(base,path):
            return [] if "/v2/orders?" in path else [{"id":"a","activity_type":"FILL","order_id":"missing","symbol":"AAPL","side":"buy"}]
        with self.assertRaises(FillHistoryBlocked):collect(api)
    def test_invalid_window(self):
        with self.assertRaises(FillHistoryBlocked):collect_window(api_fn=lambda *a:[],base="PAPER",start_utc=END,end_utc=START)
    def test_bad_limits(self):
        with self.assertRaises(FillHistoryBlocked):collect(lambda *a:[],max_pages=True)
    def test_duplicate_activity(self):
        def api(base,path):
            if "/v2/orders?" in path:return [{"id":"o","client_order_id":"intraday-abc","symbol":"AAPL"}]
            return [{"id":"x","activity_type":"FILL","order_id":"o","symbol":"AAPL","side":"buy"}]*2
        with self.assertRaises(FillHistoryBlocked):collect(api)
if __name__=="__main__":unittest.main()
