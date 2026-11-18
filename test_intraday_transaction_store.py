import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from intraday_ledger import LedgerBlocked
from intraday_transaction_store import connect, seed_session, reserve, snapshot, execution_authorized, StorageBlocked

DAY="2026-11-18"

class TransactionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"ledger.db"
        self.conn=connect(self.path)
        seed_session(self.conn,DAY)
    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()
    def test_reserve_and_reopen(self):
        reserve(self.conn,DAY,"intraday-a",20)
        self.conn.close()
        self.conn=connect(self.path)
        self.assertIn("intraday-a",snapshot(self.conn,DAY)["entries"])
    def test_duplicate_blocks(self):
        reserve(self.conn,DAY,"intraday-a",20)
        with self.assertRaises(LedgerBlocked):
            reserve(self.conn,DAY,"intraday-a",20)
    def test_duplicate_rollback_preserves_state(self):
        reserve(self.conn,DAY,"intraday-a",20)
        with self.assertRaises(LedgerBlocked):
            reserve(self.conn,DAY,"intraday-a",20)
        self.assertEqual(len(snapshot(self.conn,DAY)["entries"]),1)
    def test_uninitialized_session_blocks(self):
        with self.assertRaises(StorageBlocked):
            reserve(self.conn,"2026-11-19","intraday-a",20)
    def test_duplicate_seed_blocks(self):
        with self.assertRaises(sqlite3.IntegrityError):
            seed_session(self.conn,DAY)
    def test_max_entries_blocks(self):
        for i in range(5):
            reserve(self.conn,DAY,f"intraday-{i}",10)
        with self.assertRaises(LedgerBlocked):
            reserve(self.conn,DAY,"intraday-extra",10)
    def test_risk_budget_blocks(self):
        for i in range(4):
            reserve(self.conn,DAY,f"intraday-{i}",25)
        with self.assertRaises(LedgerBlocked):
            reserve(self.conn,DAY,"intraday-extra",1)
    def test_two_connections_one_winner(self):
        results=[]
        lock=threading.Lock()
        def worker():
            c=connect(self.path)
            try:
                reserve(c,DAY,"intraday-same",20)
                outcome="reserved"
            except LedgerBlocked:
                outcome="duplicate"
            finally:
                c.close()
            with lock:
                results.append(outcome)
        threads=[threading.Thread(target=worker) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertCountEqual(results,["reserved","duplicate"])
    def test_memory_store_rejected(self):
        with self.assertRaises(StorageBlocked):
            connect(":memory:")
    def test_execution_never_authorized(self):
        self.assertFalse(execution_authorized())

if __name__=="__main__":
    unittest.main()
