import unittest
from datetime import datetime, timezone
from intraday_session_bootstrap import validate
A={"status":"ACTIVE","trading_blocked":False,"account_blocked":False,"equity":"5000","last_equity":"5000"}
T=datetime(2026,11,18,16,tzinfo=timezone.utc)
class BootstrapTests(unittest.TestCase):
    def test_flat_account(self):
        self.assertEqual(validate(A,[],[],[],T)["equity"],5000)
    def test_positions_block(self):
        with self.assertRaises(ValueError): validate(A,[{"symbol":"AAPL"}],[],[],T)
    def test_open_orders_block(self):
        with self.assertRaises(ValueError): validate(A,[],[{"id":"x"}],[],T)
    def test_history_blocks(self):
        with self.assertRaises(ValueError): validate(A,[],[],[{"id":"x"}],T)
    def test_incomplete_history_blocks(self):
        with self.assertRaises(ValueError): validate(A,[],[],[],T,False)
    def test_loss_blocks(self):
        with self.assertRaises(ValueError): validate({**A,"equity":"4899"},[],[],[],T)
    def test_nan_blocks(self):
        with self.assertRaises(ValueError): validate({**A,"equity":"NaN"},[],[],[],T)
    def test_account_blocks(self):
        with self.assertRaises(ValueError): validate({**A,"trading_blocked":True},[],[],[],T)
    def test_naive_time_blocks(self):
        with self.assertRaises(ValueError): validate(A,[],[],[],datetime(2026,11,18))
if __name__=="__main__": unittest.main()
