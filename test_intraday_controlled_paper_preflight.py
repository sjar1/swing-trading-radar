import unittest
from intraday_controlled_paper_preflight import preflight
from intraday_durable_fill_reconciliation import DurableFillBlocked

BASE=dict(account_verified=True,broker_base="https://paper-api.alpaca.markets",
          client_order_id="intraday-manual-test-001",symbol="AMD",quantity=1,
          reference_price="100",stop_price="99",target_price="103",
          existing_intents=[],existing_open_orders=[])

class ControlledPaperPreflightTests(unittest.TestCase):
    def test_valid_is_still_blocked(self):
        x=preflight(**BASE)
        self.assertFalse(x["execution_enabled"])
        self.assertTrue(x["manual_approval_required"])
        self.assertEqual(x["broker_writes"],0)
    def test_live_base_rejected(self):
        with self.assertRaises(DurableFillBlocked):
            preflight(**(BASE|{"broker_base":"https://api.alpaca.markets"}))
    def test_multiple_shares_rejected(self):
        with self.assertRaises(DurableFillBlocked):
            preflight(**(BASE|{"quantity":2}))
    def test_open_orders_rejected(self):
        with self.assertRaises(DurableFillBlocked):
            preflight(**(BASE|{"existing_open_orders":[{"id":"existing"}]}))
    def test_existing_intent_rejected(self):
        with self.assertRaises(DurableFillBlocked):
            preflight(**(BASE|{"existing_intents":[("existing","AMD",None)]}))
    def test_weak_reward_rejected(self):
        with self.assertRaises(DurableFillBlocked):
            preflight(**(BASE|{"target_price":"102"}))
    def test_nan_rejected(self):
        with self.assertRaises(DurableFillBlocked):
            preflight(**(BASE|{"reference_price":"NaN"}))
    def test_automation_enabled_rejected(self):
        with self.assertRaises(DurableFillBlocked):
            preflight(**(BASE|{"automated_orders_enabled":True}))
    def test_account_unverified_rejected(self):
        with self.assertRaises(DurableFillBlocked):
            preflight(**(BASE|{"account_verified":False}))
if __name__=="__main__":unittest.main()
