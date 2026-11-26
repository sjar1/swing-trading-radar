import unittest
from intraday_database_readiness import inspect_database
from intraday_durable_fill_reconciliation import DurableFillBlocked
class DatabaseReadinessTests(unittest.TestCase):
    def probe(self,rows):
        return inspect_database(db_url="opaque",session_date="2026-11-18",load_fn=lambda url,day:rows)
    def test_empty_schema_is_readable_not_certified(self):
        x=self.probe([])
        self.assertEqual(x["status"],"database_readable")
        self.assertFalse(x["execution_enabled"])
        self.assertFalse(x["account_history_complete"])
    def test_valid_intent(self):
        self.assertEqual(self.probe([("intraday-a","SPY",None)])["durable_intent_count"],1)
    def test_duplicate_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            self.probe([("intraday-a","SPY",None)]*2)
    def test_bad_record_blocks(self):
        with self.assertRaises(DurableFillBlocked):self.probe([("bad","SPY",None)])
    def test_missing_database_url_blocks_before_read(self):
        def fail(*args):raise AssertionError("must not read")
        with self.assertRaises(DurableFillBlocked):
            inspect_database(db_url="",session_date="2026-11-18",load_fn=fail)
    def test_invalid_date_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            inspect_database(db_url="opaque",session_date="2026-02-30",load_fn=lambda *a:[])
    def test_database_failure_propagates(self):
        def fail(*args):raise RuntimeError("secret db exception")
        with self.assertRaises(RuntimeError):
            inspect_database(db_url="opaque",session_date="2026-11-18",load_fn=fail)
if __name__=="__main__":unittest.main()
