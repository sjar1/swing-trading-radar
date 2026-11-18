import unittest
from intraday_durable_fill_reconciliation import reconcile_session,DurableFillBlocked
I=[("intraday-a","AAPL","broker-1")]
F=[{"event_id":"event-1","client_order_id":"intraday-a","symbol":"AAPL","order_id":"broker-1"}]
class DurableFillTests(unittest.TestCase):
    def test_match(self):
        x=reconcile_session(I,F)
        self.assertTrue(x["session_consistency_verified"])
        self.assertFalse(x["position_attribution_certified"])
    def test_empty(self):self.assertEqual(reconcile_session([],[])["matched_fill_count"],0)
    def test_missing_intent(self):
        with self.assertRaises(DurableFillBlocked):reconcile_session([],F)
    def test_unacknowledged(self):
        with self.assertRaises(DurableFillBlocked):reconcile_session([("intraday-a","AAPL",None)],F)
    def test_wrong_order_id(self):
        with self.assertRaises(DurableFillBlocked):reconcile_session(I,[{**F[0],"order_id":"other"}])
    def test_wrong_symbol(self):
        with self.assertRaises(DurableFillBlocked):reconcile_session(I,[{**F[0],"symbol":"MSFT"}])
    def test_duplicate_fill(self):
        with self.assertRaises(DurableFillBlocked):reconcile_session(I,F+F)
    def test_duplicate_intent(self):
        with self.assertRaises(DurableFillBlocked):reconcile_session(I+I,F)
if __name__=="__main__":unittest.main()
