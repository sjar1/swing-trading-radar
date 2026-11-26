import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from intraday_flatten_controller import liquidation_plan

NOW=datetime(2026,11,18,15,40,tzinfo=ZoneInfo("America/New_York"))
DAY={"date":"2026-11-18","open":"09:30","close":"16:00"}
EARLY={"date":"2026-11-18","open":"09:30","close":"13:00"}
LEDGER={"version":1,"session_date":"2026-11-18","entries":{}}
ORDER={"id":"a","symbol":"SPY","client_order_id":"intraday-20261118-SPY-a","status":"new"}

class FlattenControllerTests(unittest.TestCase):
    def run_plan(self, **kw):
        return liquidation_plan(kw.get("calendar",DAY),kw.get("clock",{"is_open":True}),
                                kw.get("now",NOW),kw.get("positions",[]),
                                kw.get("orders",[]),kw.get("ledger",LEDGER),
                                kw.get("dedicated",True))
    def test_never_executes(self):
        self.assertFalse(self.run_plan()["execution_enabled"])
    def test_empty_flatten_window(self):
        self.assertEqual(self.run_plan()["reason"],"no_positions")
    def test_owned_order_proposed_for_cancel(self):
        self.assertEqual(self.run_plan(orders=[ORDER])["cancel_order_ids"],["a"])
    def test_non_dedicated_blocks(self):
        self.assertEqual(self.run_plan(dedicated=False)["reason"],"dedicated_account_not_verified")
    def test_unowned_order_blocks(self):
        self.assertEqual(self.run_plan(orders=[{**ORDER,"client_order_id":"swing-SPY"}])["reason"],"unowned_open_order")
    def test_position_blocks_without_fill_attribution(self):
        self.assertEqual(self.run_plan(positions=[{"symbol":"SPY","qty":"1"}])["reason"],"position_fill_attribution_unverified")
    def test_missing_ledger_blocks(self):
        self.assertEqual(self.run_plan(ledger=None)["reason"],"durable_ledger_unverified")
    def test_outside_window_blocks(self):
        self.assertEqual(self.run_plan(now=NOW.replace(hour=14))["reason"],"outside_flatten_window")
    def test_early_close_flatten(self):
        self.assertEqual(self.run_plan(calendar=EARLY,now=NOW.replace(hour=12,minute=40))["reason"],"no_positions")
    def test_early_close_outside_window(self):
        self.assertEqual(self.run_plan(calendar=EARLY,now=NOW.replace(hour=12,minute=10))["reason"],"outside_flatten_window")
    def test_clock_disagreement_blocks(self):
        self.assertEqual(self.run_plan(clock={"is_open":False})["reason"],"calendar_unverified")
    def test_duplicate_order_blocks(self):
        self.assertEqual(self.run_plan(orders=[ORDER,ORDER])["reason"],"duplicate_order_id")
    def test_invalid_open_order_state_blocks(self):
        self.assertEqual(self.run_plan(orders=[{**ORDER,"status":"filled"}])["reason"],"unexpected_open_order_status")

if __name__=="__main__":
    unittest.main()
