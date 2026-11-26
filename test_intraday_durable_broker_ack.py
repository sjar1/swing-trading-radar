import unittest
from intraday_durable_broker_ack import validate,persist
from intraday_durable_fill_reconciliation import DurableFillBlocked

BASE=dict(client_order_id="intraday-test-001",
          broker_order={"id":"broker-1","client_order_id":"intraday-test-001",
                        "status":"accepted","side":"buy","asset_class":"us_equity"},
          account_verified=True,broker_base="https://paper-api.alpaca.markets")
class DurableAckTests(unittest.TestCase):
    def test_valid_ack_is_not_authorization(self):
        self.assertEqual(validate(**BASE),("broker-1","accepted"))
    def test_wrong_client_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            validate(**(BASE|{"broker_order":BASE["broker_order"]|{"client_order_id":"intraday-other"}}))
    def test_missing_broker_id_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            validate(**(BASE|{"broker_order":BASE["broker_order"]|{"id":None}}))
    def test_live_endpoint_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            validate(**(BASE|{"broker_base":"https://api.alpaca.markets"}))
    def test_unverified_account_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            validate(**(BASE|{"account_verified":False}))
    def test_sell_order_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            validate(**(BASE|{"broker_order":BASE["broker_order"]|{"side":"sell"}}))
    def test_unknown_status_blocks(self):
        with self.assertRaises(DurableFillBlocked):
            validate(**(BASE|{"broker_order":BASE["broker_order"]|{"status":"mystery"}}))
    def test_missing_db_blocks_without_io(self):
        with self.assertRaises(DurableFillBlocked):
            persist(**(BASE|{"db_url":""}))
if __name__=="__main__":unittest.main()
