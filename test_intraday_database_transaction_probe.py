"""Offline tests for the rollback-only PostgreSQL probe."""
import sys
import types
import unittest
from datetime import date
from unittest.mock import patch
from intraday_database_transaction_probe import inspect

DAY=date(2026,11,18)

class Cursor:
    def __init__(self,connection):
        self.conn=connection
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,statement,params=None):
        self.conn.statements.append(statement.strip().split()[0].upper())
    def fetchone(self):
        c=self.conn
        if c.stage==0:return c.session
        if c.stage==1:
            if len(c.statements)==1:return c.session
            return ("reserved",)
        return (0,) if c.rollback_called else (1,)

class Connection:
    def __init__(self,stage,session):
        self.stage=stage;self.session=session
        self.statements=[];self.rollback_called=False
    def __enter__(self):return self
    def __exit__(self,typ,val,tb):return False
    def cursor(self):return Cursor(self)
    def rollback(self):self.rollback_called=True

class ProbeTests(unittest.TestCase):
    def fake(self,session):
        conns=[Connection(i,session) for i in range(3)]
        iterator=iter(conns)
        return conns,patch.dict(sys.modules,{"psycopg":types.SimpleNamespace(connect=lambda *a,**k:next(iterator))})
    def test_rolls_back_and_verifies_from_new_connection(self):
        conns,mock=self.fake((True,))
        with mock:result=inspect("opaque",DAY)
        self.assertEqual(result["status"],"isolated_transaction_rollback_verified")
        self.assertTrue(conns[1].rollback_called)
        self.assertEqual(conns[2].statements,["SET","SELECT"])
        self.assertEqual(result["database_writes_committed"],0)
        self.assertEqual(result["broker_writes"],0)
    def test_missing_session_does_not_insert(self):
        conns,mock=self.fake(None)
        with mock:result=inspect("opaque",DAY)
        self.assertEqual(result["status"],"blocked_session_missing")
        self.assertEqual(conns[1].statements,[])
    def test_unblocked_session_does_not_insert(self):
        conns,mock=self.fake((False,))
        with mock:
            with self.assertRaisesRegex(ValueError,"session_must_be_blocked"):
                inspect("opaque",DAY)
        self.assertEqual(conns[1].statements,[])
    def test_missing_database_url_fails_before_connection(self):
        with self.assertRaisesRegex(ValueError,"database_url_required"):
            inspect("",DAY)
if __name__=="__main__":unittest.main()
