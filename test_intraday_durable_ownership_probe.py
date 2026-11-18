import unittest
from datetime import date,datetime
from intraday_durable_ownership_probe import inspect_durable_ownership
from intraday_durable_fill_reconciliation import DurableFillBlocked
from intraday_alpaca_fills import FillHistoryBlocked
D=date(2026,11,18)
I=[("intraday-a","SPY","broker-1")]
O=[{"id":"broker-1","client_order_id":"intraday-a","symbol":"SPY"}]
class DurableOwnershipProbeTests(unittest.TestCase):
    def probe(self,orders,intents):
        return inspect_durable_ownership(db_url="unused",session_date=D,
            api_fn=lambda base,path:orders,base="PAPER",load_fn=lambda url,day:intents)
    def test_consistent_stays_read_only(self):
        x=self.probe(O,I)
        self.assertEqual(x["durably_matched_open_orders"],1)
        self.assertFalse(x["execution_enabled"])
    def test_unowned_broker_order_blocks(self):
        with self.assertRaises(DurableFillBlocked):self.probe(O,[])
    def test_missing_ack_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            self.probe(O,[("intraday-a","SPY",None)])
    def test_truncated_orders_block(self):
        with self.assertRaises(FillHistoryBlocked):self.probe([{}]*500,I)
    def test_db_failure_prevents_broker_fetch(self):
        def bad(*args):raise DurableFillBlocked("db_unavailable")
        def broker(*args):raise AssertionError("must not fetch")
        with self.assertRaises(DurableFillBlocked):
            inspect_durable_ownership(db_url="unused",session_date=D,api_fn=broker,base="PAPER",load_fn=bad)
    def test_missing_database_url_blocks_before_broker(self):
        with self.assertRaisesRegex(DurableFillBlocked,"missing_database_url"):
            inspect_durable_ownership(db_url="",session_date=D,api_fn=lambda *a:[],base="PAPER",load_fn=lambda *a:[])
    def test_datetime_not_accepted_as_session_date(self):
        with self.assertRaisesRegex(DurableFillBlocked,"invalid_session_date"):
            inspect_durable_ownership(db_url="unused",session_date=datetime(2026,11,18),api_fn=lambda *a:[],base="PAPER",load_fn=lambda *a:[])
    def test_invalid_date_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            inspect_durable_ownership(db_url="unused",session_date="2026-11-18",api_fn=lambda *a:[],base="PAPER",load_fn=lambda *a:[])
if __name__=="__main__":unittest.main()
