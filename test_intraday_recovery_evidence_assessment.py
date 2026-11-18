import unittest
from intraday_recovery_evidence_assessment import assess
from intraday_durable_fill_reconciliation import DurableFillBlocked
def evidence(n=1,compared=1,incomplete=0,unresolved=0):
    return dict(snapshot={"intents":[("intraday-a","SPY","broker-a")]*n,"snapshot_atomic":True},
                audit={"intent_count":n},
                broker_probe={"durable_intent_count":n,"matched_broker_orders":n-unresolved,"unresolved_broker_orders":unresolved,"execution_enabled":False,"broker_writes":0},
                execution_comparison={"durable_intent_count":n,"compared_order_count":compared,"incomplete_order_count":incomplete,"broker_snapshot_drift_count":0,"unresolved_broker_order_count":0,"execution_enabled":False,"broker_writes":0,"fill_history_certified":False,"historical_execution_coverage_proven":False})
class AssessmentTests(unittest.TestCase):
    def test_consistent_nonempty_is_not_authorization(self):
        x=assess(**evidence())
        self.assertTrue(x["bounded_observations_consistent"])
        self.assertFalse(x["entry_permitted"])
        self.assertFalse(x["execution_enabled"])
        self.assertFalse(x["historical_execution_coverage_proven"])
    def test_empty_not_consistent(self):
        x=assess(**evidence(n=0,compared=0))
        self.assertFalse(x["bounded_observations_consistent"])
    def test_incomplete(self):
        x=assess(**evidence(compared=0,incomplete=1))
        self.assertFalse(x["bounded_observations_consistent"])
    def test_missing_snapshot(self):
        v=evidence();v["snapshot"]["snapshot_atomic"]=False
        with self.assertRaises(DurableFillBlocked):assess(**v)
    def test_mismatched_counts(self):
        v=evidence();v["broker_probe"]["durable_intent_count"]=2
        with self.assertRaises(DurableFillBlocked):assess(**v)
    def test_unsafe_evidence(self):
        v=evidence();v["execution_comparison"]["execution_enabled"]=True
        with self.assertRaises(DurableFillBlocked):assess(**v)
    def test_false_certification(self):
        v=evidence();v["execution_comparison"]["fill_history_certified"]=True
        with self.assertRaises(DurableFillBlocked):assess(**v)
    def test_invalid_count(self):
        v=evidence();v["execution_comparison"]["compared_order_count"]=-1
        with self.assertRaises(DurableFillBlocked):assess(**v)
if __name__=="__main__":unittest.main()
