import unittest
from intraday_open_order_ownership import inspect_open_order_ownership
from intraday_durable_fill_reconciliation import DurableFillBlocked
I=[("intraday-a","SPY","broker-1")]
O=[{"id":"broker-1","client_order_id":"intraday-a","symbol":"SPY"}]
class OpenOrderOwnershipTests(unittest.TestCase):
    def test_durable_match_does_not_enable_execution(self):
        x=inspect_open_order_ownership(O,I)
        self.assertTrue(x["open_order_identity_consistent"])
        self.assertFalse(x["execution_enabled"])
    def test_empty(self):
        self.assertEqual(inspect_open_order_ownership([],[])["open_orders_observed"],0)
    def test_unknown_order(self):
        with self.assertRaisesRegex(DurableFillBlocked,"unattributed_open_order"):
            inspect_open_order_ownership(O,[])
    def test_missing_broker_ack(self):
        with self.assertRaisesRegex(DurableFillBlocked,"open_order_durable_identity_mismatch"):
            inspect_open_order_ownership(O,[("intraday-a","SPY",None)])
    def test_symbol_mismatch(self):
        with self.assertRaises(DurableFillBlocked):
            inspect_open_order_ownership(O,[("intraday-a","QQQ","broker-1")])
    def test_duplicate_open_order(self):
        with self.assertRaises(DurableFillBlocked):inspect_open_order_ownership(O+O,I)
    def test_duplicate_intent(self):
        with self.assertRaises(DurableFillBlocked):inspect_open_order_ownership(O,I+I)
    def test_missing_identity(self):
        with self.assertRaises(DurableFillBlocked):
            inspect_open_order_ownership([{"symbol":"SPY"}],I)
if __name__=="__main__":unittest.main()
