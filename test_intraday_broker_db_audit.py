import unittest
from intraday_broker_db_audit import compare
class AuditTests(unittest.TestCase):
    def test_empty_without_session(self):
        self.assertIn("durable_session_missing",compare(None,[],[],[])["problems"])
    def test_blocked_session(self):
        self.assertIn("durable_session_blocked",compare((False,),[],[],[])["problems"])
    def test_clean_still_no_execution(self):
        r=compare((True,),[],[],[])
        self.assertFalse(r["execution_enabled"])
        self.assertFalse(r["safe_to_trade"])
    def test_unknown_broker_order(self):
        self.assertIn("untracked_intraday_broker_order",compare((True,),[],[{"client_order_id":"intraday-x"}],[])["problems"])
    def test_foreign_order(self):
        self.assertIn("foreign_order_in_dedicated_account",compare((True,),[],[{"client_order_id":"other"}],[])["problems"])
    def test_missing_acknowledgement(self):
        self.assertIn("intent_without_broker_order",compare((True,),[("intraday-x","reserved")],[],[])["problems"])
    def test_position(self):
        self.assertIn("position_attribution_unverified",compare((True,),[],[],[{"symbol":"AAPL"}])["problems"])
    def test_truncated(self):
        self.assertIn("broker_history_incomplete",compare((True,),[],[],[],False)["problems"])
    def test_duplicate_broker(self):
        x=[{"client_order_id":"intraday-x"},{"client_order_id":"intraday-x"}]
        self.assertIn("duplicate_broker_client_id",compare((True,),[],x,[])["problems"])
    def test_invalid_snapshot(self):
        self.assertIn("invalid_snapshot",compare((True,),None,[],[])["problems"])
if __name__=="__main__": unittest.main()
