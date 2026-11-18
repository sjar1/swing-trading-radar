import unittest
from intraday_restart_safety import inspect_restart
from intraday_alpaca_fills import FillHistoryBlocked

class RestartSafetyTests(unittest.TestCase):
    def test_empty_but_uncertified_still_blocks(self):
        x=inspect_restart(account_verified=True,position_count=0,open_order_count=0)
        self.assertIn("history_not_certified",x["blockers"])
        self.assertFalse(x["execution_enabled"])
    def test_unowned_positions_and_orders_block(self):
        x=inspect_restart(account_verified=True,position_count=2,open_order_count=1)
        self.assertIn("positions_require_attribution",x["blockers"])
        self.assertIn("open_orders_require_reconciliation",x["blockers"])
    def test_all_clear_is_still_read_only(self):
        x=inspect_restart(account_verified=True,position_count=0,open_order_count=0,history_complete=True,attribution_certified=True)
        self.assertTrue(x["restart_clear"])
        self.assertFalse(x["entry_permitted"])
        self.assertEqual(x["broker_writes"],0)
    def test_malformed_counters_block(self):
        for value in (-1,True,"0"):
            with self.subTest(value=value),self.assertRaises(FillHistoryBlocked):
                inspect_restart(account_verified=True,position_count=value,open_order_count=0)
if __name__=="__main__":unittest.main()
