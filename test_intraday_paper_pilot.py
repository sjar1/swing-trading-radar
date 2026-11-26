import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from intraday_paper_pilot import prepare_pilot, PilotBlocked

NOW = datetime(2026, 11, 18, 11, 0, tzinfo=ZoneInfo("America/New_York"))
ACCOUNT = {"status": "ACTIVE", "equity": "5000", "last_equity": "5000", "cash": "5000"}
TRADE = {"qty": 4, "limit_price": "20.00",
         "stop_loss": {"stop_price": "19.50"},
         "take_profit": {"limit_price": "21.50"}}

class PaperPilotTests(unittest.TestCase):
    def prepare(self, **kw):
        return prepare_pilot(kw.get("symbol", "AAPL"), kw.get("trade", TRADE),
                             kw.get("account", ACCOUNT), kw.get("positions", []),
                             kw.get("orders", []), kw.get("now", NOW))

    def test_proposal_is_not_execution(self):
        payload = self.prepare()
        self.assertFalse(payload["execution_enabled"])
        self.assertEqual(payload["order_class"], "bracket")
        self.assertEqual(payload["time_in_force"], "day")
        self.assertEqual(payload["paper_endpoint"], "https://paper-api.alpaca.markets")

    def test_block_existing_position(self):
        with self.assertRaises(PilotBlocked):
            self.prepare(positions=[{"symbol": "MSFT"}])

    def test_block_existing_order(self):
        with self.assertRaises(PilotBlocked):
            self.prepare(orders=[{"symbol": "SPY"}])

    def test_block_daily_loss(self):
        with self.assertRaises(PilotBlocked):
            self.prepare(account={**ACCOUNT, "equity": "4899"})

    def test_block_excess_notional(self):
        with self.assertRaises(PilotBlocked):
            self.prepare(trade={**TRADE, "qty": 20})

    def test_block_excess_risk(self):
        with self.assertRaises(PilotBlocked):
            self.prepare(trade={**TRADE, "qty": 11, "stop_loss": {"stop_price": "17.00"}})

    def test_block_low_reward_risk(self):
        with self.assertRaises(PilotBlocked):
            self.prepare(trade={**TRADE, "take_profit": {"limit_price": "20.50"}})

    def test_block_missing_cash(self):
        with self.assertRaises(PilotBlocked):
            self.prepare(account={"status": "ACTIVE", "equity": "5000", "last_equity": "5000"})

    def test_block_after_hours(self):
        with self.assertRaises(PilotBlocked):
            self.prepare(now=NOW.replace(hour=16))

    def test_block_invalid_symbol(self):
        with self.assertRaises(PilotBlocked):
            self.prepare(symbol="INVALID")

if __name__ == "__main__":
    unittest.main()
