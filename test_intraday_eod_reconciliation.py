import unittest
from intraday_eod_reconciliation import audit
WINDOW={"flatten_due":False,"past_close":False}
ORDER={"id":"broker-1","client_order_id":"intraday-test-1","status":"accepted"}
class AuditTests(unittest.TestCase):
    def test_empty_flat(self):
        self.assertTrue(audit([],[],[],[],WINDOW)["verified"])
    def test_missing_ack(self):
        r=audit([("intraday-test-1","submitted",None)],[],[],[],WINDOW)
        self.assertFalse(r["verified"])
        self.assertTrue(any("missing_broker_acknowledgement" in x for x in r["problems"]))
    def test_reserved_ack_is_ambiguous(self):
        self.assertFalse(audit([("intraday-test-1","reserved",None)],[ORDER],[],[],WINDOW)["verified"])
    def test_ack_id_mismatch(self):
        self.assertFalse(audit([("intraday-test-1","accepted","wrong")],[ORDER],[],[],WINDOW)["verified"])
    def test_untracked_order(self):
        self.assertFalse(audit([],[ORDER],[],[],WINDOW)["verified"])
    def test_valid_ack(self):
        self.assertTrue(audit([("intraday-test-1","accepted","broker-1")],[ORDER],[],[],WINDOW)["verified"])
    def test_open_orders_at_flatten(self):
        r=audit([],[],[],[ORDER],{"flatten_due":True,"past_close":False})
        self.assertIn("open_orders_at_flatten_deadline",r["problems"])
    def test_positions_at_flatten(self):
        r=audit([],[],[{"symbol":"AAPL"}],[],{"flatten_due":True,"past_close":False})
        self.assertIn("positions_at_flatten_deadline",r["problems"])
        self.assertEqual(r["positions_closed"],0)
    def test_no_broker_writes(self):
        r=audit([],[],[],[],WINDOW)
        self.assertFalse(r["execution_enabled"])
        self.assertEqual(r["orders_submitted"],0)
        self.assertEqual(r["orders_canceled"],0)
    def test_duplicate_broker_order(self):
        self.assertFalse(audit([], [ORDER,ORDER],[],[],WINDOW)["verified"])
if __name__=="__main__": unittest.main()
