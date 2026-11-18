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
    def test_pre_window_order_matches_in_window_fill(self):
        from urllib.parse import urlparse,parse_qs
        def api(base,path):
            if "/v2/orders?" in path:
                params=parse_qs(urlparse(path).query)
                self.assertNotIn("after",params)
                self.assertNotIn("until",params)
                return [{"id":"old-order","client_order_id":"intraday-old",
                         "symbol":"AAPL","created_at":"2026-11-16T12:00:00Z"}]
            return [{"id":"fill-new","activity_type":"FILL","order_id":"old-order",
                     "symbol":"AAPL","side":"buy","transaction_time":START.isoformat()}]
        out=collect(api)
        self.assertEqual(out["fills"][0]["client_order_id"],"intraday-old")
        self.assertFalse(out["account_history_complete"])
    def test_valid_timestamp_within_window(self):
        def api(base,path):
            if "/v2/orders?" in path:
                return [{"id":"order1","client_order_id":"intraday-abc","symbol":"AAPL"}]
            return [{"id":"fill1","activity_type":"FILL","order_id":"order1",
                     "symbol":"AAPL","side":"buy","transaction_time":START.isoformat()}]
        x=collect(api)
        self.assertEqual(x["activity_count"],1)
        self.assertFalse(x["account_history_complete"])
    def test_end_boundary_rejected(self):
        def api(base,path):
            if "/v2/orders?" in path:return []
            return [{"id":"fill1","transaction_time":END.isoformat()}]
        with self.assertRaisesRegex(FillHistoryBlocked,"fill_outside_requested_window"):
            collect(api)
    def test_missing_timestamp_rejected(self):
        def api(base,path):
            if "/v2/orders?" in path:return []
            return [{"id":"fill1"}]
        with self.assertRaisesRegex(FillHistoryBlocked,"missing_fill_timestamp"):
            collect(api)
    def test_timezone_offset_accepted(self):
        from datetime import timezone,timedelta
        local=START.astimezone(timezone(timedelta(hours=-5))).isoformat()
        def api(base,path):
            if "/v2/orders?" in path:
                return [{"id":"order1","client_order_id":"intraday-abc","symbol":"AAPL"}]
            return [{"id":"fill1","activity_type":"FILL","order_id":"order1",
                     "symbol":"AAPL","side":"buy","transaction_time":local}]
        self.assertEqual(collect(api)["activity_count"],1)
    def test_interrupted_second_page_fails_closed(self):
        calls=[0]
        def api(base,path):
            if "/v2/orders?" in path:return []
            calls[0]+=1
            if calls[0]==1:return [{"id":str(i),"transaction_time":START.isoformat()} for i in range(100)]
            raise ConnectionError("network_interrupted")
        with self.assertRaises(ConnectionError):collect(api)
        self.assertEqual(calls[0],2)
    def test_repeated_page_cursor_rejected(self):
        def api(base,path):
            if "/v2/orders?" in path:return []
            return [{"id":str(i)} for i in range(100)]
        with self.assertRaises(FillHistoryBlocked):collect(api,max_pages=3)
    def test_partial_page_invalid_order_blocks(self):
        def api(base,path):
            if "/v2/orders?" in path:return [{"id":"missing-client"}]
            return []
        # Invalid order metadata must not yield a valid empty ledger.
        with self.assertRaises(FillHistoryBlocked):collect(api)
    def test_api_failure_on_orders_blocks(self):
        def api(base,path):raise TimeoutError("orders_timeout")
        with self.assertRaises(TimeoutError):collect(api)
if __name__=="__main__":unittest.main()
