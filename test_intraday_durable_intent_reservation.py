import unittest
from datetime import date
from intraday_durable_intent_reservation import reserve
from intraday_durable_fill_reconciliation import DurableFillBlocked

BASE=dict(db_url="opaque",session_date=date(2026,11,18),
          client_order_id="intraday-manual-001",symbol="AMD",
          strategy="opening_range_breakout",reserved_risk="1.00",
          expected_account_verified=True,broker_base="https://paper-api.alpaca.markets")

class ReservationTests(unittest.TestCase):
    def reject(self,**changes):
        with self.assertRaises(DurableFillBlocked):
            reserve(**(BASE|changes))
    def test_no_account_verification(self):self.reject(expected_account_verified=False)
    def test_live_endpoint(self):self.reject(broker_base="https://api.alpaca.markets")
    def test_risk_nan(self):self.reject(reserved_risk="NaN")
    def test_risk_over_limit(self):self.reject(reserved_risk="25.01")
    def test_bad_client(self):self.reject(client_order_id="swing-001")
    def test_bad_strategy(self):self.reject(strategy="unknown")
    def test_bad_symbol(self):self.reject(symbol="amd")
    def test_missing_db(self):self.reject(db_url="")
if __name__=="__main__":unittest.main()
