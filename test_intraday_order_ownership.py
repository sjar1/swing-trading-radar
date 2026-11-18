import unittest
from intraday_order_ownership import verify_order_ownership,verify_flatten_readiness,OwnershipBlocked
I={"client_order_id":"intraday-abc","broker_order_id":"broker-1","symbol":"AAPL"}
O={"client_order_id":"intraday-abc","id":"broker-1","symbol":"AAPL"}
class OwnershipTests(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(verify_order_ownership([O],[I])["owned_open_order_ids"],["broker-1"])
    def test_prefix_not_enough(self):
        with self.assertRaises(OwnershipBlocked):verify_order_ownership([O],[])
    def test_broker_id_mismatch(self):
        with self.assertRaises(OwnershipBlocked):verify_order_ownership([{**O,"id":"other"}],[I])
    def test_symbol_mismatch(self):
        with self.assertRaises(OwnershipBlocked):verify_order_ownership([{**O,"symbol":"MSFT"}],[I])
    def test_duplicate_broker(self):
        with self.assertRaises(OwnershipBlocked):verify_order_ownership([O,O],[I])
    def test_duplicate_intent(self):
        with self.assertRaises(OwnershipBlocked):verify_order_ownership([O],[I,I])
    def test_positions_block(self):
        with self.assertRaises(OwnershipBlocked):verify_flatten_readiness([{"symbol":"AAPL","qty":"1"}],[],[I],[])
    def test_empty_snapshot(self):
        self.assertTrue(verify_flatten_readiness([],[],[],[])["no_positions"])
if __name__=="__main__":unittest.main()
