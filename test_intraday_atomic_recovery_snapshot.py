import unittest,sys
from unittest.mock import MagicMock,patch
from intraday_atomic_recovery_snapshot import project,load_atomic_snapshot
from intraday_durable_fill_reconciliation import DurableFillBlocked
class AtomicSnapshotTests(unittest.TestCase):
    def test_empty(self):
        x=project([])
        self.assertFalse(x["snapshot_atomic"])
        self.assertEqual(x["intents"],[])
        self.assertFalse(x["execution_enabled"])
    def test_multiple_events_one_intent(self):
        rows=[("intraday-a","SPY","broker-a","filled",1,"broker-a","partially_filled",None,{"event_type":"fill","execution_id":"x","fill_qty":"1"}),
              ("intraday-a","SPY","broker-a","filled",2,"broker-a","filled",None,{"event_type":"fill","execution_id":"y","fill_qty":"1"})]
        x=project(rows)
        self.assertEqual(len(x["intents"]),1)
        self.assertEqual(len(x["event_rows"]),2)
        self.assertEqual(len(x["execution_rows"]),2)
    def test_conflicting_identity(self):
        with self.assertRaises(DurableFillBlocked):
            project([("intraday-a","SPY","broker-a","filled",None,None,None,None,None),
                     ("intraday-a","QQQ","broker-a","filled",None,None,None,None,None)])
    def test_conflicting_state(self):
        with self.assertRaises(DurableFillBlocked):
            project([("intraday-a","SPY","broker-a","accepted",1,"broker-a","new",None,{}),
                     ("intraday-a","SPY","broker-a","filled",2,"broker-a","filled",None,{})])
    def test_duplicate_event_id(self):
        with self.assertRaises(DurableFillBlocked):
            project([("intraday-a","SPY","broker-a","accepted",1,"broker-a","new",None,{}),
                     ("intraday-a","SPY","broker-a","accepted",1,"broker-a","new",None,{})])
    def test_loader_repeatable_read_only_transaction(self):
        cur=MagicMock()
        cur.fetchall.return_value=[("intraday-a","SPY",None,"reserved",None,None,None,None,None)]
        conn=MagicMock()
        conn.__enter__.return_value=conn
        conn.cursor.return_value.__enter__.return_value=cur
        psycopg=MagicMock()
        psycopg.connect.return_value=conn
        with patch.dict(sys.modules,{"psycopg":psycopg}):
            x=load_atomic_snapshot("opaque","2026-11-18",max_rows=3)
        self.assertTrue(x["snapshot_atomic"])
        self.assertEqual(len(x["intents"]),1)
        self.assertEqual(cur.execute.call_args_list[0].args[0],"SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        self.assertEqual(cur.execute.call_args_list[1].args[1],("2026-11-18",4))
        psycopg.connect.assert_called_once_with("opaque",connect_timeout=8,sslmode="require")
    def test_loader_row_limit_blocks(self):
        cur=MagicMock()
        cur.fetchall.return_value=[("intraday-a","SPY",None,"reserved",None,None,None,None,None)]*2
        conn=MagicMock()
        conn.__enter__.return_value=conn
        conn.cursor.return_value.__enter__.return_value=cur
        psycopg=MagicMock()
        psycopg.connect.return_value=conn
        with patch.dict(sys.modules,{"psycopg":psycopg}):
            with self.assertRaises(DurableFillBlocked):
                load_atomic_snapshot("opaque","2026-11-18",max_rows=1)
    def test_invalid_row(self):
        with self.assertRaises(DurableFillBlocked):project([("bad",)])
if __name__=="__main__":unittest.main()
