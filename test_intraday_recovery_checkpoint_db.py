import unittest
from datetime import datetime,timezone,timedelta,date
from intraday_recovery_journal import RecoveryJournal
from intraday_recovery_checkpoint_db import validate_checkpoint,make_checkpoint,CheckpointBlocked,read_checkpoint
NOW=datetime(2026,11,18,15,0,tzinfo=timezone.utc)
class Cursor:
    def __init__(self,rows):self.rows=rows;self.sql=""
    def execute(self,sql,*args):self.sql+=sql+";"
    def fetchall(self):return self.rows
    def __enter__(self):return self
    def __exit__(self,*a):pass
class Conn:
    def __init__(self,rows):self.cur=Cursor(rows)
    def cursor(self):return self.cur
class CheckpointTests(unittest.TestCase):
    def test_fresh(self):
        p=make_checkpoint("2026-11-18",RecoveryJournal())
        x=validate_checkpoint(p,session_date="2026-11-18",max_age_seconds=90,observed_at=NOW,now=NOW)
        self.assertFalse(x["execution_enabled"])
    def test_stale(self):
        p=make_checkpoint("2026-11-18",RecoveryJournal())
        with self.assertRaises(CheckpointBlocked):validate_checkpoint(p,session_date="2026-11-18",max_age_seconds=90,observed_at=NOW-timedelta(seconds=91),now=NOW)
    def test_future(self):
        p=make_checkpoint("2026-11-18",RecoveryJournal())
        with self.assertRaises(CheckpointBlocked):validate_checkpoint(p,session_date="2026-11-18",max_age_seconds=90,observed_at=NOW+timedelta(seconds=1),now=NOW)
    def test_wrong_session(self):
        p=make_checkpoint("2026-11-17",RecoveryJournal())
        with self.assertRaises(CheckpointBlocked):validate_checkpoint(p,session_date="2026-11-18",max_age_seconds=90,observed_at=NOW,now=NOW)
    def test_tampered(self):
        p=make_checkpoint("2026-11-18",RecoveryJournal());p["state"]["flat_confirmed"]=True
        with self.assertRaises(CheckpointBlocked):validate_checkpoint(p,session_date="2026-11-18",max_age_seconds=90,observed_at=NOW,now=NOW)
    def test_read_only(self):
        conn=Conn([])
        self.assertIsNone(read_checkpoint(conn,date(2026,11,18)))
        self.assertIn("SET TRANSACTION READ ONLY",conn.cur.sql)
        self.assertNotIn("INSERT",conn.cur.sql)
    def test_duplicate(self):
        with self.assertRaises(CheckpointBlocked):read_checkpoint(Conn([(1,2),(3,4)]),date(2026,11,18))
if __name__=="__main__":unittest.main()
