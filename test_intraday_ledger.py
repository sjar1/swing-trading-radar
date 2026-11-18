import unittest
from intraday_ledger import order_key, validate_ledger, propose_reservation, execution_ready, LedgerBlocked

DAY = "2026-11-18"
BAR = "2026-11-18T15:46:00Z"
def blank():
    return {"version": 1, "session_date": DAY, "entries": {}}

class LedgerTests(unittest.TestCase):
    def test_stable_key(self):
        a = order_key(DAY, "AAPL", "vwap_reclaim", BAR)
        b = order_key(DAY, "AAPL", "vwap_reclaim", "2026-11-18T10:46:00-05:00")
        self.assertEqual(a, b)
    def test_key_changes_for_strategy(self):
        self.assertNotEqual(order_key(DAY, "AAPL", "vwap_reclaim", BAR),
                            order_key(DAY, "AAPL", "opening_range_breakout", BAR))
    def test_reject_naive_bar(self):
        with self.assertRaises(LedgerBlocked):
            order_key(DAY, "AAPL", "vwap_reclaim", "2026-11-18T10:46:00")
    def test_missing_ledger_blocks(self):
        with self.assertRaises(LedgerBlocked):
            validate_ledger(None, DAY)
    def test_session_mismatch_blocks(self):
        with self.assertRaises(LedgerBlocked):
            validate_ledger(blank(), "2026-11-19")
    def test_duplicate_reservation_blocks(self):
        key = order_key(DAY, "AAPL", "vwap_reclaim", BAR)
        saved = propose_reservation(blank(), DAY, key, 20)
        with self.assertRaises(LedgerBlocked):
            propose_reservation(saved, DAY, key, 20)
    def test_reservation_does_not_mutate_input(self):
        original = blank()
        key = order_key(DAY, "AAPL", "vwap_reclaim", BAR)
        proposed = propose_reservation(original, DAY, key, 20)
        self.assertEqual(original["entries"], {})
        self.assertEqual(proposed["entries"][key]["state"], "reserved")
    def test_daily_entry_cap(self):
        ledger = blank()
        for i in range(5):
            ledger["entries"][f"intraday-test-{i}"] = {"state": "closed", "reserved_risk": 10}
        with self.assertRaises(LedgerBlocked):
            propose_reservation(ledger, DAY, "intraday-test-next", 10)
    def test_daily_risk_cap(self):
        ledger = blank()
        for i in range(4):
            ledger["entries"][f"intraday-test-{i}"] = {"state": "closed", "reserved_risk": 25}
        with self.assertRaises(LedgerBlocked):
            propose_reservation(ledger, DAY, "intraday-test-next", 1)
    def test_unknown_state_blocks(self):
        ledger = blank()
        ledger["entries"]["intraday-test"] = {"state": "mystery", "reserved_risk": 1}
        with self.assertRaises(LedgerBlocked):
            validate_ledger(ledger, DAY)
    def test_execution_requires_all_safeguards(self):
        self.assertFalse(execution_ready(True, True, True, False, True))
        self.assertTrue(execution_ready(True, True, True, True, True))

if __name__ == "__main__":
    unittest.main()
