import unittest
from datetime import datetime,timezone
from intraday_pilot_preflight import evaluate
NOW=datetime(2026,11,18,17,tzinfo=timezone.utc)
ACCOUNT={"status":"ACTIVE","trading_blocked":False,"account_blocked":False}
SESSION=(5000,5010,5005,5,True,2)
class PreflightTests(unittest.TestCase):
    def test_clean_blocked_session(self):
        self.assertTrue(evaluate(ACCOUNT,[],[],[],SESSION,[],NOW)["preflight_passed"])
    def test_existing_order(self):
        self.assertFalse(evaluate(ACCOUNT,[],[{"id":"x"}],[],SESSION,[],NOW)["preflight_passed"])
    def test_existing_intent(self):
        self.assertFalse(evaluate(ACCOUNT,[],[],[],SESSION,[("x",)],NOW)["preflight_passed"])
    def test_unblocked_is_unsafe(self):
        self.assertFalse(evaluate(ACCOUNT,[],[],[],(5000,5000,5000,0,False,0),[],NOW)["preflight_passed"])
    def test_missing_session(self):
        self.assertFalse(evaluate(ACCOUNT,[],[],[],None,[],NOW)["preflight_passed"])
    def test_no_execution(self):
        result=evaluate(ACCOUNT,[],[],[],SESSION,[],NOW)
        self.assertFalse(result["execution_enabled"])
        self.assertEqual(result["orders_submitted"],0)
if __name__=="__main__":unittest.main()
