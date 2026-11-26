import unittest
from decimal import Decimal
from intraday_session_verify import verify
S=(Decimal("5000"),Decimal("5000"),Decimal("5000"),Decimal("0"),True,0)
class VerifyTests(unittest.TestCase):
    def test_valid(self): self.assertTrue(verify(S,[("time",Decimal("5000"))],[])["verified"])
    def test_missing(self): self.assertFalse(verify(None,[],[])["verified"])
    def test_unblocked(self): self.assertFalse(verify((*S[:4],False,0),[("time",5000)],[])["verified"])
    def test_missing_sample(self): self.assertFalse(verify(S,[],[])["verified"])
    def test_mismatched_sample(self): self.assertFalse(verify(S,[("time",4999)],[])["verified"])
    def test_intent(self): self.assertFalse(verify(S,[("time",5000)],[("x",)])["verified"])
    def test_peak(self): self.assertFalse(verify((5000,4999,5000,0,True,0),[("time",5000)],[])["verified"])
    def test_no_execution(self): self.assertFalse(verify(S,[("time",5000)],[])["execution_enabled"])
if __name__=="__main__": unittest.main()
