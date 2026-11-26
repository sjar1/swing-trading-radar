import unittest
from intraday_recovery_scenarios import simulate
INTENT=("intraday-test","SPY","broker-1")
ORDER={"id":"broker-1","client_order_id":"intraday-test","symbol":"SPY"}
POSITION={"symbol":"SPY","qty":"0.5"}
class RecoveryScenariosTests(unittest.TestCase):
    def assert_no_trading(self,result):
        self.assertFalse(result["restart_clear"])
        self.assertFalse(result["entry_permitted"])
        self.assertFalse(result["execution_enabled"])
        self.assertEqual(result["broker_writes"],0)
    def test_clean_restart_still_blocked_without_lifetime_proof(self):
        r=simulate()
        self.assertEqual(r["outcome"],"observed")
        self.assertIn("history_not_certified",r["blockers"])
        self.assert_no_trading(r)
    def test_pending_order_after_crash(self):
        r=simulate(orders=[ORDER],intents=[INTENT])
        self.assertEqual(r["outcome"],"observed")
        self.assertIn("open_orders_require_reconciliation",r["blockers"])
        self.assert_no_trading(r)
    def test_partially_filled_order_and_position(self):
        r=simulate(orders=[ORDER],intents=[INTENT],positions=[POSITION])
        self.assertEqual(r["outcome"],"observed")
        self.assertIn("positions_require_attribution",r["blockers"])
        self.assert_no_trading(r)
    def test_unknown_broker_order(self):
        r=simulate(orders=[ORDER])
        self.assertEqual(r["outcome"],"blocked")
        self.assert_no_trading(r)
    def test_unacknowledged_broker_order(self):
        r=simulate(orders=[ORDER],intents=[("intraday-test","SPY",None)])
        self.assertEqual(r["outcome"],"blocked")
        self.assert_no_trading(r)
    def test_api_failure_during_order_reconciliation(self):
        r=simulate(fail_path="/v2/orders")
        self.assertEqual(r["reason"],"SimulatedBrokerFailure")
        self.assert_no_trading(r)
    def test_api_failure_during_position_reconciliation(self):
        r=simulate(fail_path="/v2/positions")
        self.assertEqual(r["reason"],"SimulatedBrokerFailure")
        self.assert_no_trading(r)
    def test_account_mismatch_blocks_before_orders(self):
        r=simulate(expected_account_id="other-account")
        self.assertEqual(r["outcome"],"blocked")
        self.assertEqual(r["read_count"],1)
        self.assert_no_trading(r)
    def test_duplicate_broker_orders_block(self):
        r=simulate(orders=[ORDER,ORDER],intents=[INTENT])
        self.assertEqual(r["outcome"],"blocked")
        self.assert_no_trading(r)
if __name__=="__main__":unittest.main()
