import unittest
from datetime import datetime,timezone
from intraday_observation_bundle import inspect_bundle
from intraday_durable_fill_reconciliation import DurableFillBlocked
from intraday_alpaca_fills import FillHistoryBlocked
T=datetime(2026,11,18,20,tzinfo=timezone.utc)
def api(base,path):
    if path=="/v2/account":return {"id":"paper-id"}
    return []
def window(**kw):
    return {"window_exhausted":True,
        "window_start":kw["start_utc"].isoformat(),
        "window_end":kw["end_utc"].isoformat(),
        "fills":[],"activity_count":0}
class ObservationBundleTests(unittest.TestCase):
    def probe(self,load_fn=lambda *a:[],history_fn=window):
        return inspect_bundle(db_url="opaque",session_date=T.date(),
            api_fn=api,base="PAPER",expected_account_id="paper-id",
            now=T,load_fn=load_fn,history_fn=history_fn)
    def test_empty_observation_still_blocks(self):
        x=self.probe()
        self.assertTrue(x["window_coverage_verified"])
        self.assertFalse(x["restart_clear"])
        self.assertFalse(x["account_history_complete"])
        self.assertFalse(x["execution_enabled"])
    def test_missing_history_fails_closed(self):
        def bad(**kw):return {**window(**kw),"window_exhausted":False}
        with self.assertRaises(FillHistoryBlocked):self.probe(history_fn=bad)
    def test_unmatched_fill_blocks(self):
        def bad(**kw):
            return {**window(**kw),"fills":[{"event_id":"e","client_order_id":"intraday-a","symbol":"SPY","order_id":"b"}]}
        with self.assertRaises(DurableFillBlocked):self.probe(history_fn=bad)
    def test_invalid_time_blocks(self):
        with self.assertRaises(FillHistoryBlocked):
            inspect_bundle(db_url="opaque",session_date=T.date(),api_fn=api,base="PAPER",
                expected_account_id="paper-id",now=T.replace(tzinfo=None),load_fn=lambda *a:[])
if __name__=="__main__":unittest.main()
