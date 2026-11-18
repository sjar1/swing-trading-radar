import unittest
from datetime import datetime,timezone,timedelta
from intraday_reconciliation_health import evaluate,ReconciliationHealthBlocked
NOW=datetime(2026,11,18,15,0,tzinfo=timezone.utc)
def evidence():
    return {"observed_at":NOW.isoformat(),"session_history_exhausted":True,
        "session_consistency_verified":True,"account_history_complete":True,
        "position_attribution_certified":True,"broker_snapshot_complete":True,
        "durable_intents_verified":True,"unmatched_fills":0,"unattributed_positions":0}
class HealthTests(unittest.TestCase):
    def test_complete(self):
        self.assertFalse(evaluate(evidence(),now=NOW)["execution_enabled"])
    def test_session_only_insufficient(self):
        e=evidence();e["account_history_complete"]=False
        with self.assertRaises(ReconciliationHealthBlocked):evaluate(e,now=NOW)
    def test_unmatched(self):
        e=evidence();e["unmatched_fills"]=1
        with self.assertRaises(ReconciliationHealthBlocked):evaluate(e,now=NOW)
    def test_missing_count(self):
        e=evidence();e.pop("unattributed_positions")
        with self.assertRaises(ReconciliationHealthBlocked):evaluate(e,now=NOW)
    def test_stale(self):
        e=evidence();e["observed_at"]=(NOW-timedelta(seconds=91)).isoformat()
        with self.assertRaises(ReconciliationHealthBlocked):evaluate(e,now=NOW)
    def test_future(self):
        e=evidence();e["observed_at"]=(NOW+timedelta(seconds=1)).isoformat()
        with self.assertRaises(ReconciliationHealthBlocked):evaluate(e,now=NOW)
    def test_missing_timestamp(self):
        e=evidence();e.pop("observed_at")
        with self.assertRaises(ReconciliationHealthBlocked):evaluate(e,now=NOW)
    def test_false_not_truthy(self):
        e=evidence();e["durable_intents_verified"]=1
        with self.assertRaises(ReconciliationHealthBlocked):evaluate(e,now=NOW)
if __name__=="__main__":unittest.main()
