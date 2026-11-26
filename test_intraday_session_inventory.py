import unittest
from datetime import date
from intraday_session_inventory import validate,inspect
from intraday_durable_fill_reconciliation import DurableFillBlocked

class SessionInventoryTests(unittest.TestCase):
    def test_empty(self):
        x=validate([],20)
        self.assertEqual(x["nonempty_session_count"],0)
        self.assertFalse(x["entry_permitted"])
    def test_nonempty_counts_without_ids(self):
        x=validate([(date(2026,11,17),2,3),(date(2026,11,16),1,0)],20)
        self.assertEqual(x["nonempty_session_count"],2)
        self.assertEqual(x["sessions"][0]["persisted_event_count"],3)
        self.assertNotIn("client_order_id",str(x))
    def test_reject_negative_count(self):
        with self.assertRaises(DurableFillBlocked):
            validate([(date(2026,11,17),-1,0)],20)
    def test_reject_unsorted_dates(self):
        with self.assertRaises(DurableFillBlocked):
            validate([(date(2026,11,16),1,0),(date(2026,11,17),1,0)],20)
    def test_reject_excess_rows(self):
        with self.assertRaises(DurableFillBlocked):
            validate([(date(2026,11,17),0,0)]*2,1)
    def test_reject_invalid_limits(self):
        with self.assertRaises(DurableFillBlocked):
            inspect("opaque",as_of=date(2026,11,18),max_sessions=31)
if __name__=="__main__":unittest.main()
