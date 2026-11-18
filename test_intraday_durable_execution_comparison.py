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
    def test_zero_fill_without_execution_not_certified(self):
        x=run([row()],lambda *args:{**broker(),"status":"new","filled_qty":"0"})
        self.assertEqual(x["compared_order_count"],0)
        self.assertFalse(x["persisted_fill_quantity_compared"])
        self.assertFalse(x["snapshot_atomic"])
    def test_excessive_event_rows_fail_closed(self):
        with self.assertRaises(DurableFillBlocked):
            run([row()]*2001)
    def test_untyped_fill_quantity_marks_incomplete(self):
        x=run([row(1,"new",{"fill_qty":"0.5"},"broker-one"),
               row(2,"partially_filled",{"event_type":"fill","execution_id":"exec-2","fill_qty":"0.5"},"broker-one")])
        self.assertEqual(x["compared_order_count"],0)
        self.assertEqual(x["incomplete_order_count"],1)
    def test_broker_fill_changes_between_reads(self):
        calls=[0]
        def moving(*args):
            calls[0]+=1
            return {**broker(),"filled_qty":"0.5" if calls[0]==1 else "0.75"}
        x=run([row(1,"partially_filled",{"event_type":"fill","execution_id":"exec-1","fill_qty":"0.5"},"broker-one")],moving)
        self.assertEqual(x["broker_snapshot_drift_count"],1)
        self.assertEqual(x["compared_order_count"],0)
    def test_broker_status_changes_between_reads(self):
        calls=[0]
        def moving(*args):
            calls[0]+=1
            return {**broker(),"status":"partially_filled" if calls[0]==1 else "filled"}
        x=run([row(1,"partially_filled",{"event_type":"fill","execution_id":"exec-1","fill_qty":"0.5"},"broker-one")],moving)
        self.assertEqual(x["broker_snapshot_drift_count"],1)
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
