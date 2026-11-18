import unittest
from intraday_recovery_simulator import Recovery,RecoveryBlocked
class RecoveryTests(unittest.TestCase):
    def test_cancel_then_flat(self):
        r=Recovery()
        self.assertEqual(r.plan(["o1"],{"AAPL":2},snapshot_complete=True,ownership_verified=True)["broker_writes"],0)
        with self.assertRaises(RecoveryBlocked):r.close_plan({"AAPL":2},snapshot_complete=True,ownership_verified=True)
        r.observe_cancellations([],snapshot_complete=True)
        self.assertEqual(r.close_plan({"AAPL":2},snapshot_complete=True,ownership_verified=True)["would_close"],{"AAPL":2})
        self.assertTrue(r.observe_flat({},[],snapshot_complete=True)["flat"])
    def test_partial_fill_during_cancel_blocks(self):
        r=Recovery();r.plan(["o1"],{"AAPL":2},snapshot_complete=True,ownership_verified=True)
        r.observe_cancellations([],snapshot_complete=True)
        with self.assertRaises(RecoveryBlocked):r.close_plan({"AAPL":3},snapshot_complete=True,ownership_verified=True)
    def test_cancel_unconfirmed(self):
        r=Recovery();r.plan(["o1"],{},snapshot_complete=True,ownership_verified=True)
        with self.assertRaises(RecoveryBlocked):r.observe_cancellations(["o1"],snapshot_complete=True)
    def test_unowned_snapshot(self):
        with self.assertRaises(RecoveryBlocked):Recovery().plan(["o1"],{},snapshot_complete=True)
    def test_duplicate_order(self):
        with self.assertRaises(RecoveryBlocked):Recovery().plan(["o1","o1"],{},snapshot_complete=True,ownership_verified=True)
    def test_missing_cancel_snapshot(self):
        r=Recovery();r.plan(["o1"],{},snapshot_complete=True,ownership_verified=True)
        with self.assertRaises(RecoveryBlocked):r.observe_cancellations([])
    def test_unconfirmed_flat(self):
        r=Recovery();r.plan([],{"AAPL":1},snapshot_complete=True,ownership_verified=True)
        r.close_plan({"AAPL":1},snapshot_complete=True,ownership_verified=True)
        with self.assertRaises(RecoveryBlocked):r.observe_flat({"AAPL":1},[],snapshot_complete=True)
    def test_no_orders_no_positions(self):
        r=Recovery();r.plan([],{},snapshot_complete=True,ownership_verified=True)
        self.assertEqual(r.close_plan({},snapshot_complete=True,ownership_verified=True)["broker_writes"],0)
        self.assertEqual(r.phase,"flat")
if __name__=="__main__":unittest.main()
