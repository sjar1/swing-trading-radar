import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from intraday_engine import evaluate, plan, gate

class EngineTests(unittest.TestCase):
    def test_opening_breakout(self):
        bars=[{"o":20,"h":20.1,"l":19.9,"c":20,"v":100} for _ in range(15)]
        bars += [{"o":20,"h":20.08,"l":19.98,"c":20.02,"v":100} for _ in range(6)]
        bars.append({"o":20.02,"h":20.3,"l":20,"c":20.25,"v":500})
        signal,reason=evaluate(bars)
        self.assertEqual(reason,"qualified")
        self.assertEqual(signal["strategy"],"opening_range_breakout")
    def test_no_setup(self):
        bars=[{"o":20,"h":20.1,"l":19.9,"c":20,"v":100} for _ in range(22)]
        self.assertIsNone(evaluate(bars)[0])
    def test_risk_sizing(self):
        p=plan({"price":20,"stop":19.5},5000,2000)
        self.assertLessEqual(p["qty"]*(float(p["limit_price"])-19.5),25.01)
        self.assertLessEqual(p["qty"]*float(p["limit_price"]),1000)
    def test_daily_loss(self):
        now=datetime(2026,11,18,11,0,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(gate({"status":"ACTIVE","equity":"4899","last_equity":"5000","cash":"5000"},[],[],0,now),"daily_loss_limit")
    def test_position_limit(self):
        now=datetime(2026,11,18,11,0,tzinfo=ZoneInfo("America/New_York"))
        a={"status":"ACTIVE","equity":"5000","last_equity":"5000","cash":"5000"}
        self.assertEqual(gate(a,[{"symbol":"A"},{"symbol":"B"}],[],0,now),"position_limit")
    def test_entry_limit(self):
        now=datetime(2026,11,18,11,0,tzinfo=ZoneInfo("America/New_York"))
        a={"status":"ACTIVE","equity":"5000","last_equity":"5000","cash":"5000"}
        self.assertEqual(gate(a,[],[],5,now),"entry_limit")

    def test_dedicated_intraday_credentials(self):
        import inspect, intraday_engine
        source=inspect.getsource(intraday_engine.api)
        self.assertIn('ALPACA_INTRADAY_API_KEY',source)
        self.assertIn('ALPACA_INTRADAY_API_SECRET',source)
        self.assertNotIn('os.environ["ALPACA_API_KEY"]',source)
        self.assertNotIn('os.environ["ALPACA_API_SECRET"]',source)

    def test_execution_fail_closed_design(self):
        import inspect, intraday_engine
        source=inspect.getsource(intraday_engine.main)
        self.assertIn('execution_not_certified',source)
        self.assertNotIn('api(PAPER,"/v2/orders","POST"',source)
    def test_missing_cash_blocks(self):
        now=datetime(2026,11,18,11,0,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(gate({"status":"ACTIVE","equity":"5000","last_equity":"5000"},[],[],0,now),"invalid_cash")
    def test_after_hours_blocks(self):
        now=datetime(2026,11,18,16,0,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(gate({"status":"ACTIVE","equity":"5000","last_equity":"5000","cash":"5000"},[],[],0,now),"outside_entry_window")

if __name__=="__main__": unittest.main()
