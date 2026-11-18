import unittest
from intraday_fill_attribution import attribute_positions,AttributionBlocked
I=[{"client_order_id":"intraday-a","symbol":"AAPL"}]
F=[{"event_id":"f1","client_order_id":"intraday-a","symbol":"AAPL","side":"buy","qty":"3"}]
P=[{"symbol":"AAPL","side":"long","qty":"3"}]
def check(p=P,f=F,i=I,**kw):
    return attribute_positions(p,f,i,fills_complete=True,dedicated_account=True,**kw)
class AttributionTests(unittest.TestCase):
    def test_exact_fill(self):self.assertEqual(check()["positions"],{"AAPL":"3"})
    def test_partial_close(self):
        self.assertEqual(check([{"symbol":"AAPL","side":"long","qty":"1"}],F+[{"event_id":"f2","client_order_id":"intraday-a","symbol":"AAPL","side":"sell","qty":"2"}])["positions"],{"AAPL":"1"})
    def test_flat(self):
        self.assertTrue(check([],F+[{"event_id":"f2","client_order_id":"intraday-a","symbol":"AAPL","side":"sell","qty":"3"}])["verified"])
    def test_incomplete_history(self):
        with self.assertRaises(AttributionBlocked):attribute_positions(P,F,I,dedicated_account=True)
    def test_not_dedicated(self):
        with self.assertRaises(AttributionBlocked):attribute_positions(P,F,I,fills_complete=True)
    def test_mismatched_qty(self):
        with self.assertRaises(AttributionBlocked):check([{"symbol":"AAPL","side":"long","qty":"2"}])
    def test_unowned_fill(self):
        with self.assertRaises(AttributionBlocked):check(f=[{**F[0],"client_order_id":"intraday-other"}])
    def test_duplicate_fill(self):
        with self.assertRaises(AttributionBlocked):check(f=F+F)
    def test_short_position(self):
        with self.assertRaises(AttributionBlocked):check(p=[{**P[0],"side":"short"}])
    def test_over_sell(self):
        with self.assertRaises(AttributionBlocked):check(f=F+[{"event_id":"f2","client_order_id":"intraday-a","symbol":"AAPL","side":"sell","qty":"4"}])
    def test_missing_position(self):
        with self.assertRaises(AttributionBlocked):check(p=[])
    def test_invalid_quantity(self):
        with self.assertRaises(AttributionBlocked):check(f=[{**F[0],"qty":"NaN"}])
if __name__=="__main__":unittest.main()
