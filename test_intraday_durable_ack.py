import unittest
from intraday_durable_ack import next_action,TransitionBlocked,transition
class DurableAckTests(unittest.TestCase):
    def test_reserved(self):self.assertEqual(next_action("reserved",None),"mark_unknown_before_any_submission")
    def test_unknown_never_retries(self):self.assertEqual(next_action("unknown",None),"manual_broker_reconciliation_no_retry")
    def test_accepted(self):self.assertEqual(next_action("accepted","b"),"observe_broker_only")
    def test_filled(self):self.assertEqual(next_action("filled","b"),"do_not_resubmit")
    def test_invalid_state(self):
        with self.assertRaises(TransitionBlocked):next_action("mystery",None)
    def test_missing_broker_evidence(self):
        with self.assertRaises(TransitionBlocked):transition(None,"intraday-x","accepted")
    def test_invalid_id(self):
        with self.assertRaises(TransitionBlocked):transition(None,"bad","unknown")
    def test_invalid_target(self):
        with self.assertRaises(TransitionBlocked):transition(None,"intraday-x","reserved")
if __name__=="__main__":unittest.main()
