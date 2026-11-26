import unittest
from datetime import datetime, timezone
from intraday_reconciliation import reconcile

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)

class ReconciliationTests(unittest.TestCase):
    def test_empty_snapshot_still_blocks(self):
        self.assertEqual(reconcile([], [], NOW)["reason"], "durable_execution_ledger_missing")
    def test_owned_active_order_blocks(self):
        order = {"id": "1", "client_order_id": "intraday-20261118-SPY",
                 "status": "new"}
        self.assertEqual(reconcile([order], [], NOW)["reason"], "owned_order_still_active")
    def test_position_blocks_even_with_filled_order(self):
        order = {"id": "1", "client_order_id": "intraday-20261118-SPY",
                 "status": "filled"}
        self.assertEqual(reconcile([order], [{"symbol": "SPY"}], NOW)["reason"],
                         "position_ownership_unverified")
    def test_duplicate_id_blocks(self):
        order = {"id": "1", "client_order_id": "intraday-a", "status": "filled"}
        self.assertEqual(reconcile([order, order], [], NOW)["reason"], "duplicate_order_id")
    def test_unknown_status_blocks(self):
        order = {"id": "1", "client_order_id": "intraday-a", "status": "mystery"}
        self.assertEqual(reconcile([order], [], NOW)["reason"], "unknown_order_status")
    def test_missing_fields_blocks(self):
        self.assertEqual(reconcile([{"id": "1"}], [], NOW)["reason"], "incomplete_order")
    def test_naive_clock_blocks(self):
        self.assertEqual(reconcile([], [], datetime(2026, 11, 18))["reason"], "naive_timestamp")

if __name__ == "__main__":
    unittest.main()
