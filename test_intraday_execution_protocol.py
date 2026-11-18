import unittest
from intraday_execution_protocol import PilotState,SafetyStop
class ProtocolTests(unittest.TestCase):
    def test_submit_once(self):
        s=PilotState("intraday-1")
        self.assertEqual(s.submit_attempt()["broker_writes"],0)
        with self.assertRaises(SafetyStop):s.submit_attempt()
    def test_timeout_never_retry(self):
        s=PilotState("intraday-1");s.submit_attempt()
        self.assertFalse(s.timeout()["retry_allowed"])
        with self.assertRaises(SafetyStop):s.submit_attempt()
    def test_ack_mismatch(self):
        s=PilotState("intraday-1");s.submit_attempt()
        with self.assertRaises(SafetyStop):s.acknowledge("b1","wrong")
    def test_ack_success(self):
        s=PilotState("intraday-1");s.submit_attempt();s.acknowledge("b1","intraday-1")
        self.assertEqual(s.broker_id,"b1")
    def test_unattributed_position(self):
        s=PilotState("intraday-1");s.submit_attempt();s.acknowledge("b1","intraday-1");s.fill(1)
        with self.assertRaises(SafetyStop):s.flatten_plan([],False,True)
    def test_incomplete_snapshot(self):
        with self.assertRaises(SafetyStop):PilotState("intraday-1").flatten_plan([],True,False)
    def test_cancel_before_close(self):
        s=PilotState("intraday-1");s.submit_attempt();s.acknowledge("b1","intraday-1");s.fill(1)
        s.flatten_plan(["b1"],True,True)
        with self.assertRaises(SafetyStop):s.close_plan(["b1"],True)
        with self.assertRaises(SafetyStop):s.cancel_ack(["b1"])
        s.cancel_ack([])
        self.assertEqual(s.close_plan([],True)["close_qty"],1)
        self.assertTrue(s.close_ack([],[])["flat"])
    def test_partial_close_not_flat(self):
        s=PilotState("intraday-1");s.submit_attempt();s.acknowledge("b1","intraday-1");s.fill(2)
        s.flatten_plan([],True,True);s.close_plan([],True)
        with self.assertRaises(SafetyStop):s.close_ack([{"qty":"1"}],[])
    def test_unknown_submission_blocks_flatten(self):
        s=PilotState("intraday-1");s.submit_attempt();s.timeout()
        with self.assertRaises(SafetyStop):s.flatten_plan([],True,True)
    def test_no_broker_writes(self):
        s=PilotState("intraday-1")
        self.assertEqual(s.submit_attempt()["broker_writes"],0)
if __name__=="__main__":unittest.main()
