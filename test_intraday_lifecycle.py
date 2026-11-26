import unittest
from datetime import datetime, timedelta, timezone
from intraday_lifecycle import owned_orders, flatten_plan, account_risk

class LifecycleTests(unittest.TestCase):
    def test_only_owned_orders(self):
        orders=[{"id":"a","client_order_id":"intraday-20261118-SPY-open"},
                {"id":"b","client_order_id":"swing-SPY"}]
        self.assertEqual([o["id"] for o in owned_orders(orders)],["a"])
    def test_close_window_plans_only_owned_cancels(self):
        now=datetime(2026,11,18,20,40,tzinfo=timezone.utc)
        orders=[{"id":"a","client_order_id":"intraday-20261118-SPY-open"},
                {"id":"b","client_order_id":"swing-SPY"}]
        plan=flatten_plan([{"symbol":"SPY"}],orders,now,now+timedelta(minutes=20))
        self.assertEqual(plan["proposed_cancel_order_ids"],["a"])
        self.assertEqual(plan["proposed_close_positions"],[])
        self.assertTrue(plan["requires_manual_reconciliation"])
        self.assertFalse(plan["execution_enabled"])
    def test_no_early_cancel(self):
        now=datetime(2026,11,18,17,tzinfo=timezone.utc)
        plan=flatten_plan([], [{"id":"a","client_order_id":"intraday-test"}],now,now+timedelta(hours=4))
        self.assertEqual(plan["proposed_cancel_order_ids"],[])
    def test_missing_peak_blocks(self):
        a={"equity":"5000","last_equity":"5000","cash":"5000"}
        self.assertEqual(account_risk(a)["reason"],"missing_durable_peak_equity")
    def test_drawdown_blocks(self):
        a={"equity":"4900","last_equity":"5000","cash":"4900"}
        self.assertEqual(account_risk(a,peak_equity=5010)["reason"],"daily_drawdown")
    def test_risk_budget_blocks(self):
        a={"equity":"5000","last_equity":"5000","cash":"5000"}
        self.assertEqual(account_risk(a,peak_equity=5000,active_risk=51)["reason"],"risk_budget")

if __name__=="__main__": unittest.main()
