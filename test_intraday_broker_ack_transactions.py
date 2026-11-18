"""Mocked database transaction tests; never connects to a real database."""
import sys,types,unittest
from unittest.mock import patch
from intraday_durable_broker_ack import persist
from intraday_durable_fill_reconciliation import DurableFillBlocked

ORDER={"id":"broker-one","client_order_id":"intraday-test-001",
       "status":"accepted","side":"buy","asset_class":"us_equity"}
ARGS=dict(db_url="opaque",client_order_id="intraday-test-001",broker_order=ORDER,
          account_verified=True,broker_base="https://paper-api.alpaca.markets")

class Cursor:
    def __init__(self,existing=("broker-one","accepted"),events=()):
        self.existing=existing;self.events=events;self.sql=[]
    def execute(self,sql,params):
        self.sql.append(sql.strip().split()[0].upper())
    def fetchone(self):return self.existing
    def fetchall(self):return self.events
    def __enter__(self):return self
    def __exit__(self,*args):pass

class Connection:
    def __init__(self,cursor,fail_commit=False):
        self.c=cursor;self.fail_commit=fail_commit;self.committed=False
    def cursor(self):return self.c
    def __enter__(self):return self
    def __exit__(self,typ,val,tb):
        if self.fail_commit and typ is None:raise OSError("ambiguous commit")
        self.committed=typ is None

class AckPersistenceTests(unittest.TestCase):
    def run_case(self,cursor,fail_commit=False):
        conn=Connection(cursor,fail_commit)
        fake=types.SimpleNamespace(connect=lambda *a,**k:conn)
        with patch.dict(sys.modules,{"psycopg":fake}):
            try:return persist(**ARGS),conn
            finally:self.conn=conn
    def test_valid_commits_without_broker_write(self):
        result,conn=self.run_case(Cursor())
        self.assertTrue(conn.committed)
        self.assertEqual(conn.c.sql,["SELECT","SELECT","UPDATE","INSERT"])
        self.assertFalse(result["retry_submission"])
        self.assertEqual(result["broker_writes"],0)
    def test_conflicting_intent_blocks_before_update(self):
        with self.assertRaises(DurableFillBlocked):
            self.run_case(Cursor(existing=("other-broker","accepted")))
        self.assertFalse(self.conn.committed)
        self.assertEqual(self.conn.c.sql,["SELECT"])
    def test_conflicting_event_blocks_before_update(self):
        with self.assertRaises(DurableFillBlocked):
            self.run_case(Cursor(events=[("other-broker","accepted")]))
        self.assertFalse(self.conn.committed)
        self.assertEqual(self.conn.c.sql,["SELECT","SELECT"])
    def test_terminal_event_blocks_before_update(self):
        with self.assertRaises(DurableFillBlocked):
            self.run_case(Cursor(events=[("broker-one","filled")]))
        self.assertFalse(self.conn.committed)
        self.assertEqual(self.conn.c.sql,["SELECT","SELECT"])
    def test_missing_intent_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            self.run_case(Cursor(existing=None))
        self.assertFalse(self.conn.committed)
    def test_commit_ambiguity_blocks_retry(self):
        with self.assertRaisesRegex(DurableFillBlocked,"acknowledgement_commit_unknown_reconcile_before_retry"):
            self.run_case(Cursor(),fail_commit=True)
        self.assertFalse(self.conn.committed)
if __name__=="__main__":unittest.main()
