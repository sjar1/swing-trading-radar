import unittest
from datetime import date
from unittest.mock import patch
from intraday_recovery_journal import RecoveryJournal
from intraday_recovery_checkpoint_write import persist_isolated,CheckpointWriteBlocked
class Cursor:
    def __init__(self,rows):self.rows=rows;self.calls=[]
    def execute(self,*args):self.calls.append(args)
    def fetchall(self):return self.rows
    def __enter__(self):return self
    def __exit__(self,*args):pass
class Conn:
    def __init__(self,rows):self.cur=Cursor(rows)
    def cursor(self):return self.cur
class WriteTests(unittest.TestCase):
    def test_production_schema_rejected(self):
        c=Conn([(1,)])
        with self.assertRaises(CheckpointWriteBlocked):persist_isolated(c,schema="intraday_paper",session_date=date(2026,11,18),state=RecoveryJournal(),expected_revision=0)
        self.assertFalse(c.cur.calls)
    def test_bad_schema_rejected(self):
        with self.assertRaises(CheckpointWriteBlocked):persist_isolated(Conn([]),schema="intraday_test_foo;drop",session_date=date(2026,11,18),state=RecoveryJournal(),expected_revision=0)
    def test_stale_revision_rejected(self):
        with self.assertRaises(CheckpointWriteBlocked):persist_isolated(Conn([]),schema="intraday_test_1234567890abcdef",session_date=date(2026,11,18),state=RecoveryJournal(),expected_revision=0)
    def test_valid_isolated_cas(self):
        x=persist_isolated(Conn([(1,)]),schema="intraday_test_1234567890abcdef",session_date=date(2026,11,18),state=RecoveryJournal(),expected_revision=0)
        self.assertEqual(x["revision"],1)
        self.assertFalse(x["execution_enabled"])
    def test_negative_revision_rejected(self):
        with self.assertRaises(CheckpointWriteBlocked):persist_isolated(Conn([]),schema="intraday_test_1234567890abcdef",session_date=date(2026,11,18),state=RecoveryJournal(),expected_revision=-1)
if __name__=="__main__":unittest.main()
