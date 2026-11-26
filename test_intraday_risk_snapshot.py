import unittest
from intraday_risk_snapshot import assess,RiskBlocked
A={"status":"ACTIVE","trading_blocked":False,"account_blocked":False,"equity":"5000","last_equity":"5000","cash":"5000"}
class RiskTests(unittest.TestCase):
    def test_normal(self):
        x=assess(A,[],[])
        self.assertTrue(x["within_limits"])
        self.assertFalse(x["entry_permitted"])
    def test_daily_loss(self):
        self.assertIn("daily_loss_limit",assess({**A,"equity":"4900"},[],[])["problems"])
    def test_exposure(self):
        self.assertIn("exposure_limit",assess(A,[{"symbol":"AAPL","side":"long","market_value":"2000"}],[])["problems"])
    def test_position_limit(self):
        p=[{"symbol":s,"side":"long","market_value":"100"} for s in ("AAPL","MSFT")]
        self.assertIn("position_limit",assess(A,p,[])["problems"])
    def test_missing_price(self):
        with self.assertRaises(RiskBlocked):assess(A,[],[{"symbol":"AAPL","side":"buy","qty":"1"}])
    def test_invalid_account(self):
        with self.assertRaises(RiskBlocked):assess({**A,"trading_blocked":True},[],[])
    def test_nan(self):
        with self.assertRaises(RiskBlocked):assess({**A,"equity":"NaN"},[],[])
    def test_duplicate(self):
        p={"symbol":"AAPL","side":"long","market_value":"10"}
        with self.assertRaises(RiskBlocked):assess(A,[p,p],[])
    def test_pending_buy_exposure(self):
        x=assess(A,[],[{"symbol":"AAPL","side":"buy","qty":"2","limit_price":"100"}])
        self.assertEqual(x["exposure"],"200")
if __name__=="__main__":unittest.main()
