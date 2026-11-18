import unittest
from intraday_durable_execution_comparison import compare_rows
from intraday_durable_fill_reconciliation import DurableFillBlocked
I="intraday-one"
def row(eid=None,status=None,payload=None,broker_event=None):
    return (I,"SPY","broker-one",eid,status,payload,broker_event)
def broker(*args):
    return {"client_order_id":I,"id":"broker-one","symbol":"SPY","status":"partially_filled","filled_qty":"0.5"}
def run(rows,reader=broker):
    return compare_rows(rows=rows,api_fn=reader,base="PAPER")
class ExecutionComparisonTests(unittest.TestCase):
    def test_empty(self):
        x=run([])
        self.assertEqual(x["compared_order_count"],0)
        self.assertFalse(x["execution_enabled"])
    def test_matching_explicit_execution(self):
        x=run([row(1,"partially_filled",{"event_type":"fill","execution_id":"exec-1","fill_qty":"0.50"},"broker-one")])
        self.assertEqual(x["compared_order_count"],1)
        self.assertFalse(x["fill_history_certified"])
    def test_mismatch(self):
        with self.assertRaises(DurableFillBlocked):
            run([row(1,"partially_filled",{"event_type":"fill","execution_id":"exec-1","fill_qty":"0.4"},"broker-one")])
    def test_duplicate_execution(self):
        with self.assertRaises(DurableFillBlocked):
            run([row(1,"partially_filled",{"event_type":"fill","execution_id":"exec-1","fill_qty":"0.25"},"broker-one"),
                 row(2,"partially_filled",{"event_type":"fill","execution_id":"exec-1","fill_qty":"0.25"},"broker-one")])
    def test_cumulative_snapshot_not_increment(self):
        x=run([row(1,"partially_filled",{"filled_qty":"0.5"},"broker-one")])
        self.assertEqual(x["incomplete_order_count"],1)
        self.assertFalse(x["persisted_fill_quantity_compared"])
    def test_missing_execution_id(self):
        with self.assertRaises(DurableFillBlocked):
            run([row(1,"filled",{"event_type":"fill","fill_qty":"0.5"},"broker-one")])
    def test_missing_fill_payload(self):
        with self.assertRaises(DurableFillBlocked):
            run([row(1,"filled",None,"broker-one")])
    def test_unrecorded_broker_fill(self):
        x=run([row()])
        self.assertEqual(x["incomplete_order_count"],1)
    def test_broker_network_failure_unresolved(self):
        def fail(*args):raise RuntimeError("offline")
        x=run([row()],fail)
        self.assertEqual(x["incomplete_order_count"],1)
    def test_invalid_negative_increment(self):
        with self.assertRaises(Exception):
            run([row(1,"filled",{"event_type":"fill","execution_id":"exec-1","fill_qty":"-1"},"broker-one")])
if __name__=="__main__":unittest.main()
