import unittest
from intraday_window_ledger import merge_windows,WindowLedgerBlocked
A="2026-11-17T14:00:00+00:00"
B="2026-11-17T15:00:00+00:00"
C="2026-11-17T16:00:00+00:00"
def w(start,end,fills=None):
    f=[] if fills is None else fills
    return {"window_start":start,"window_end":end,"window_exhausted":True,
            "fills":f,"activity_count":len(f)}
def fill(id,when):return {"event_id":id,"transaction_time":when}
class LedgerTests(unittest.TestCase):
    def test_contiguous(self):
        out=merge_windows([w(A,B,[fill("a",A)]),w(B,C,[fill("b",B)])])
        self.assertEqual(out["fill_count"],2)
        self.assertFalse(out["account_history_complete"])
        self.assertFalse(out["execution_enabled"])
    def test_gap(self):
        with self.assertRaises(WindowLedgerBlocked):merge_windows([w(A,B),w(C,"2026-11-17T17:00:00+00:00")])
    def test_overlap(self):
        with self.assertRaises(WindowLedgerBlocked):merge_windows([w(A,C),w(B,C)])
    def test_duplicate(self):
        with self.assertRaises(WindowLedgerBlocked):merge_windows([w(A,B,[fill("a",A)]),w(B,C,[fill("a",B)])])
    def test_unexhausted(self):
        x=w(A,B);x["window_exhausted"]=False
        with self.assertRaises(WindowLedgerBlocked):merge_windows([x])
    def test_outside(self):
        with self.assertRaises(WindowLedgerBlocked):merge_windows([w(A,B,[fill("a",B)])])
    def test_bad_count(self):
        x=w(A,B);x["activity_count"]=1
        with self.assertRaises(WindowLedgerBlocked):merge_windows([x])
    def test_empty_rejected(self):
        with self.assertRaises(WindowLedgerBlocked):merge_windows([])
    def test_naive_time_rejected(self):
        with self.assertRaises(WindowLedgerBlocked):merge_windows([w("2026-11-17T14:00:00",B)])
if __name__=="__main__":unittest.main()
