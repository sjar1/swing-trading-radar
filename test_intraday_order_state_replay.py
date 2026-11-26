import unittest
from intraday_order_state_replay import replay,ReplayBlocked
ID="intraday-test"
def e(n,kind,**kw):return {"event_id":str(n),"client_order_id":ID,"type":kind,**kw}
S=e(1,"submission_attempted")
A=e(2,"acknowledged",broker_order_id="broker-1")
class ReplayTests(unittest.TestCase):
    def check(self,events):
        x=replay(client_order_id=ID,events=events)
        self.assertFalse(x["restart_clear"])
        self.assertFalse(x["execution_enabled"])
        self.assertEqual(x["broker_writes"],0)
        return x
    def test_empty_is_reserved_and_blocked(self):
        self.assertEqual(self.check([])["phase"],"reserved")
    def test_timeout_requires_reconciliation(self):
        x=self.check([S,e(2,"submission_timeout")])
        self.assertTrue(x["requires_broker_reconciliation"])
    def test_acknowledged_pending_requires_reconciliation(self):
        self.assertTrue(self.check([S,A])["requires_broker_reconciliation"])
    def test_partial_then_filled(self):
        x=self.check([S,A,e(3,"partially_filled",broker_order_id="broker-1",fill_qty="0.5"),
                      e(4,"filled",broker_order_id="broker-1",fill_qty="0.5")])
        self.assertEqual(x["filled_quantity"],"1.0")
        self.assertEqual(x["phase"],"filled")
    def test_cancel_after_partial_fill(self):
        x=self.check([S,A,e(3,"partially_filled",broker_order_id="broker-1",fill_qty="0.5"),e(4,"canceled")])
        self.assertEqual(x["phase"],"canceled")
        self.assertEqual(x["filled_quantity"],"0.5")
    def test_duplicate_event_blocks(self):
        with self.assertRaises(ReplayBlocked):self.check([S,S])
    def test_fill_without_ack_blocks(self):
        with self.assertRaises(ReplayBlocked):self.check([S,e(2,"filled",broker_order_id="broker-1",fill_qty="1")])
    def test_mismatched_broker_fill_blocks(self):
        with self.assertRaises(ReplayBlocked):self.check([S,A,e(3,"filled",broker_order_id="other",fill_qty="1")])
    def test_zero_fill_blocks(self):
        with self.assertRaises(ReplayBlocked):self.check([S,A,e(3,"filled",broker_order_id="broker-1",fill_qty="0")])
    def test_wrong_client_blocks(self):
        with self.assertRaises(ReplayBlocked):self.check([{"event_id":"1","client_order_id":"intraday-other","type":"submission_attempted"}])
    def test_terminal_replay_blocks(self):
        with self.assertRaises(ReplayBlocked):self.check([S,A,e(3,"canceled"),e(4,"acknowledged",broker_order_id="broker-1")])
if __name__=="__main__":unittest.main()
