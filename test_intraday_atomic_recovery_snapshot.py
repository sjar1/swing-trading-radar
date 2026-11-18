import unittest
from intraday_atomic_recovery_snapshot import project
from intraday_durable_fill_reconciliation import DurableFillBlocked
class AtomicSnapshotTests(unittest.TestCase):
    def test_empty(self):
        x=project([])
        self.assertTrue(x["snapshot_atomic"])
        self.assertEqual(x["intents"],[])
        self.assertFalse(x["execution_enabled"])
    def test_multiple_events_one_intent(self):
        rows=[("intraday-a","SPY","broker-a","filled",1,"broker-a","partially_filled",None,{"event_type":"fill","execution_id":"x","fill_qty":"1"}),
              ("intraday-a","SPY","broker-a","filled",2,"broker-a","filled",None,{"event_type":"fill","execution_id":"y","fill_qty":"1"})]
        x=project(rows)
        self.assertEqual(len(x["intents"]),1)
        self.assertEqual(len(x["event_rows"]),2)
        self.assertEqual(len(x["execution_rows"]),2)
    def test_conflicting_identity(self):
        with self.assertRaises(DurableFillBlocked):
            project([("intraday-a","SPY","broker-a","filled",None,None,None,None,None),
                     ("intraday-a","QQQ","broker-a","filled",None,None,None,None,None)])
    def test_conflicting_state(self):
        with self.assertRaises(DurableFillBlocked):
            project([("intraday-a","SPY","broker-a","accepted",1,"broker-a","new",None,{}),
                     ("intraday-a","SPY","broker-a","filled",2,"broker-a","filled",None,{})])
    def test_invalid_row(self):
        with self.assertRaises(DurableFillBlocked):project([("bad",)])
if __name__=="__main__":unittest.main()
