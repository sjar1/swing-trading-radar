import unittest
from intraday_postgres_store import reserve, ReservationBlocked, execution_authorized

class FakeCursor:
    def __init__(self, session=(False,), usage=(0, 0), inserted=("ok",)):
        self.answers = [session, usage, inserted]
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, query, params):
        self.calls.append((query, params))
    def fetchone(self): return self.answers.pop(0)

class FakeConn:
    def __init__(self, cursor): self.c = cursor
    def transaction(self): return self
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def cursor(self): return self.c

ARGS = ("2026-11-18", "intraday-20261118-AAPL-abc", "AAPL", "vwap_reclaim", 25)

class PostgresStoreTests(unittest.TestCase):
    def test_reserve(self):
        c = FakeCursor()
        self.assertEqual(reserve(FakeConn(c), *ARGS), ARGS[1])
        self.assertIn("FOR UPDATE", c.calls[0][0])
        self.assertIn("ON CONFLICT DO NOTHING", c.calls[2][0])
    def test_missing_session(self):
        with self.assertRaises(ReservationBlocked):
            reserve(FakeConn(FakeCursor(session=None)), *ARGS)
    def test_blocked_session(self):
        with self.assertRaises(ReservationBlocked):
            reserve(FakeConn(FakeCursor(session=(True,))), *ARGS)
    def test_entry_limit(self):
        with self.assertRaises(ReservationBlocked):
            reserve(FakeConn(FakeCursor(usage=(5,0))), *ARGS)
    def test_risk_limit(self):
        with self.assertRaises(ReservationBlocked):
            reserve(FakeConn(FakeCursor(usage=(4,90))), *ARGS)
    def test_duplicate(self):
        with self.assertRaises(ReservationBlocked):
            reserve(FakeConn(FakeCursor(inserted=None)), *ARGS)
    def test_bad_risk(self):
        for x in (0,26,float("nan"),"oops"):
            with self.subTest(x=x), self.assertRaises(ReservationBlocked):
                reserve(FakeConn(FakeCursor()), *ARGS[:-1], x)
    def test_bad_symbol(self):
        with self.assertRaises(ReservationBlocked):
            reserve(FakeConn(FakeCursor()), ARGS[0], ARGS[1], "aapl", ARGS[3], 25)
    def test_db_error(self):
        with self.assertRaises(ReservationBlocked):
            reserve(None, *ARGS)
    def test_no_execution(self):
        self.assertFalse(execution_authorized())
if __name__ == "__main__":
    unittest.main()
