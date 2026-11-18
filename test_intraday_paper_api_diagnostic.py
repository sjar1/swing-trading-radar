import unittest
from datetime import datetime,timezone
from intraday_paper_api_diagnostic import inspect
from intraday_alpaca_fills import FillHistoryBlocked
NOW=datetime(2026,11,18,20,tzinfo=timezone.utc)
class ApiDiagnosticTests(unittest.TestCase):
    def test_empty_window_is_not_certified(self):
        x=inspect(api_fn=lambda base,path:[],now=NOW)
        self.assertEqual(x["status"],"window_observed")
        self.assertFalse(x["account_history_complete"])
        self.assertFalse(x["reconciliation_heartbeat_healthy"])
        self.assertFalse(x["execution_enabled"])
    def test_reject_truncated_orders(self):
        def api(base,path):return [{}]*500 if "/v2/orders?" in path else []
        with self.assertRaises(FillHistoryBlocked):inspect(api_fn=api,now=NOW)
    def test_network_error_propagates_without_approval(self):
        def api(base,path):raise TimeoutError("private broker error")
        with self.assertRaises(TimeoutError):inspect(api_fn=api,now=NOW)
    def test_invalid_observation_time(self):
        with self.assertRaises(FillHistoryBlocked):
            inspect(api_fn=lambda *a:[],now=NOW.replace(tzinfo=None))
if __name__=="__main__":unittest.main()
