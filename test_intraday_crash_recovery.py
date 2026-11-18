import unittest
from intraday_crash_recovery import recovery_plan

DAY="2026-11-18"
KEY="intraday-20261118-AAPL-123"
def ledger(state="submitted"):
    return {"version":1,"session_date":DAY,"entries":{KEY:{"state":state,"reserved_risk":20}}}
def order(status="accepted"):
    return {"id":"broker-1","client_order_id":KEY,"status":status}

class CrashRecoveryTests(unittest.TestCase):
    def test_missing_ledger_blocks(self):
        self.assertEqual(recovery_plan(None,DAY,[],[])["reason"],"invalid_or_missing_durable_ledger")
    def test_missing_broker_snapshot_blocks(self):
        self.assertEqual(recovery_plan(ledger(),DAY,None,[])["reason"],"incomplete_broker_snapshot")
    def test_missing_broker_order_never_retries(self):
        r=recovery_plan(ledger(),DAY,[],[])
        self.assertFalse(r["retry_submission"])
        self.assertEqual(r["reason"],"manual_reconciliation_required")
    def test_submitted_order_requires_review(self):
        self.assertEqual(recovery_plan(ledger(),DAY,[order()],[])["reason"],"manual_reconciliation_required")
    def test_reserved_but_acknowledged_requires_review(self):
        self.assertEqual(recovery_plan(ledger("reserved"),DAY,[order()],[])["reason"],"manual_reconciliation_required")
    def test_partial_fill_requires_review(self):
        self.assertEqual(recovery_plan(ledger("partially_filled"),DAY,[order("partially_filled")],[])["reason"],"manual_reconciliation_required")
    def test_unknown_broker_order_blocks(self):
        self.assertEqual(recovery_plan({"version":1,"session_date":DAY,"entries":{}},DAY,[order()],[])["reason"],"unrecorded_broker_orders")
    def test_position_blocks(self):
        self.assertEqual(recovery_plan(ledger(),DAY,[order()],[{"symbol":"AAPL","qty":"1"}])["reason"],"position_attribution_unverified")
    def test_duplicate_order_id_blocks(self):
        duplicate={**order(),"client_order_id":"intraday-another"}
        self.assertEqual(recovery_plan(ledger(),DAY,[order(),duplicate],[])["reason"],"duplicate_broker_order")
    def test_terminal_record_read_only(self):
        r=recovery_plan(ledger("closed"),DAY,[order("filled")],[])
        self.assertEqual(r["reason"],"read_only_reconciliation_complete")
        self.assertFalse(r["execution_enabled"])
        self.assertFalse(r["safe_to_trade"])
    def test_terminal_record_open_broker_order_blocks(self):
        self.assertEqual(recovery_plan(ledger("closed"),DAY,[order("accepted")],[])["reason"],"manual_reconciliation_required")
    def test_never_authorizes_submission(self):
        self.assertFalse(recovery_plan({"version":1,"session_date":DAY,"entries":{}},DAY,[],[])["execution_enabled"])

if __name__=="__main__":
    unittest.main()
