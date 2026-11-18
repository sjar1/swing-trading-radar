import unittest
from datetime import datetime,timezone
from intraday_execution_adapter import execution_gate,proposal,AdapterBlocked
NOW=datetime(2026,11,18,16,30,tzinfo=timezone.utc)
ACCOUNT={"status":"ACTIVE","equity":"5000","last_equity":"5000","cash":"5000"}
SESSION=(5000,5000,5000,0,True,0)
CAL={"date":"2026-11-18","open":"09:30","close":"16:00"}
TRADE={"qty":1,"limit_price":"100.00","stop_loss":{"stop_price":"99.00"},"take_profit":{"limit_price":"103.00"}}
class AdapterTests(unittest.TestCase):
    def test_execution_cannot_be_enabled(self):
        with self.assertRaises(AdapterBlocked):
            execution_gate(dry_run=False,session_blocked=True,flatten_verified=True,reconciliation_verified=True)
    def test_unblocked_rejected(self):
        with self.assertRaises(AdapterBlocked):
            execution_gate(dry_run=True,session_blocked=False)
    def test_dry_run_has_no_writes(self):
        result=proposal(ACCOUNT,[],[],[],SESSION,[],CAL,{"is_open":True},"AAPL",TRADE,NOW.isoformat(),NOW)
        self.assertEqual(result["orders_submitted"],0)
        self.assertEqual(result["persisted_reservations"],0)
        self.assertEqual(result["planned_risk"],"1.00")
        self.assertFalse(result["execution_enabled"])
    def test_duplicate_intent_rejected(self):
        with self.assertRaises(AdapterBlocked):
            proposal(ACCOUNT,[],[],[],SESSION,[("intraday-x",)],CAL,{"is_open":True},"AAPL",TRADE,NOW.isoformat(),NOW)
    def test_closed_market_rejected(self):
        with self.assertRaises(Exception):
            proposal(ACCOUNT,[],[],[],SESSION,[],CAL,{"is_open":False},"AAPL",TRADE,NOW.isoformat(),NOW)
    def test_existing_position_rejected(self):
        with self.assertRaises(AdapterBlocked):
            proposal(ACCOUNT,[{"symbol":"AAPL"}],[],[],SESSION,[],CAL,{"is_open":True},"AAPL",TRADE,NOW.isoformat(),NOW)
if __name__=="__main__": unittest.main()
