"""Cross-component PAPER order lifecycle contract tests; no broker writes."""
import unittest
from unittest.mock import patch
from intraday_execution_protocol import PilotState,SafetyStop
from intraday_broker_recovery import inspect
from intraday_durable_ack import next_action
from intraday_eod_reconciliation import audit

CLIENT="intraday-integration-1"
BROKER={"id":"broker-integration-1","client_order_id":CLIENT,"status":"accepted"}
WINDOW={"flatten_due":False,"past_close":False}

class LifecycleIntegrationTests(unittest.TestCase):
    def test_submission_timeout_never_retries_even_if_broker_missing(self):
        state=PilotState(CLIENT)
        state.submit_attempt()
        state.timeout()
        with patch("intraday_broker_recovery.api",side_effect=TimeoutError):
            recovery=inspect(CLIENT,"unknown")
        self.assertFalse(recovery["retry_submission"])
        self.assertEqual(next_action("unknown",None),"manual_broker_reconciliation_no_retry")
        with self.assertRaises(SafetyStop):state.submit_attempt()
        self.assertFalse(audit([(CLIENT,"unknown",None)],[],[],[],WINDOW)["verified"])

    def test_acknowledged_then_flatten_sequence(self):
        state=PilotState(CLIENT)
        state.submit_attempt()
        with patch("intraday_broker_recovery.api",return_value=BROKER):
            recovery=inspect(CLIENT,"unknown")
        self.assertTrue(recovery["reconciled"])
        self.assertFalse(recovery["retry_submission"])
        state.acknowledge(recovery["broker_order_id"],CLIENT)
        self.assertTrue(audit([(CLIENT,"accepted",BROKER["id"])],[BROKER],[],[],WINDOW)["verified"])
        state.fill(2)
        plan=state.flatten_plan([BROKER["id"]],True,True)
        self.assertEqual(plan["broker_writes"],0)
        with self.assertRaises(SafetyStop):state.close_plan([BROKER["id"]],True)
        state.cancel_ack([])
        self.assertEqual(state.close_plan([],True)["close_qty"],2)
        with self.assertRaises(SafetyStop):state.close_ack([{"symbol":"AAPL","qty":"1"}],[])
        self.assertTrue(state.close_ack([],[])["flat"])

    def test_untracked_order_blocks_reconciliation(self):
        result=audit([],[BROKER],[],[],WINDOW)
        self.assertFalse(result["verified"])
        self.assertEqual(result["orders_submitted"],0)

    def test_unattributed_position_blocks_flatten(self):
        state=PilotState(CLIENT)
        state.submit_attempt()
        state.acknowledge(BROKER["id"],CLIENT)
        state.fill(1)
        with self.assertRaises(SafetyStop):state.flatten_plan([],False,True)

    def test_open_order_at_deadline_blocks_audit(self):
        result=audit([(CLIENT,"accepted",BROKER["id"])],[BROKER],[],[BROKER],{"flatten_due":True,"past_close":False})
        self.assertIn("open_orders_at_flatten_deadline",result["problems"])
        self.assertFalse(result["execution_enabled"])

if __name__=="__main__":
    unittest.main()
