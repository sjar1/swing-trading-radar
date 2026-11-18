import unittest
from decimal import Decimal
from intraday_equity_monitor import transition,EquityMonitorBlocked
S=(Decimal("5000"),Decimal("5000"),Decimal("5000"),Decimal("0"),True,0)
class EquityMonitorTests(unittest.TestCase):
    def test_normal_update(self):
        x=transition(S,"5010","5000")
        self.assertEqual(x["peak"],5010)
        self.assertTrue(x["blocked"])
    def test_peak_drawdown(self):
        x=transition((5000,5100,5100,0,False,2),4999,5000)
        self.assertEqual(x["drawdown"],101)
        self.assertTrue(x["blocked"])
    def test_prior_close_loss(self):
        self.assertTrue(transition((5000,5000,5000,0,False,0),4900,5000)["blocked"])
    def test_no_unblock(self):
        self.assertTrue(transition(S,5100,5000)["blocked"])
    def test_revision(self):
        self.assertEqual(transition(S,5000,5000)["revision"],1)
    def test_mismatch(self):
        with self.assertRaises(EquityMonitorBlocked): transition(S,5000,4990)
    def test_missing(self):
        with self.assertRaises(EquityMonitorBlocked): transition(None,5000,5000)
    def test_invalid(self):
        for value in ("NaN",-1,True):
            with self.subTest(value=value),self.assertRaises(EquityMonitorBlocked):
                transition(S,value,5000)
    def test_peak_never_decreases(self):
        self.assertEqual(transition((5000,5100,5050,50,True,1),5070,5000)["peak"],5100)
    def test_drawdown_sticky(self):
        self.assertEqual(transition((5000,5100,5000,100,True,1),5100,5000)["drawdown"],100)
if __name__=="__main__": unittest.main()
