import unittest
from datetime import datetime,timezone,timedelta
from intraday_monitor_health import evaluate_health,require_monitor_health,MonitorBlocked,REQUIRED
NOW=datetime(2026,11,18,15,0,tzinfo=timezone.utc)
def sample():
    return {name:{"healthy":True,"observed_at":NOW.isoformat()} for name in REQUIRED}
class MonitorHealthTests(unittest.TestCase):
    def test_healthy_still_disables_execution(self):
        x=evaluate_health(sample(),NOW)
        self.assertTrue(x["healthy"])
        self.assertFalse(x["entry_permitted"])
        self.assertFalse(x["execution_enabled"])
    def test_missing_component(self):
        s=sample();del s["broker"]
        self.assertIn("broker:missing",evaluate_health(s,NOW)["problems"])
    def test_unhealthy_component(self):
        s=sample();s["risk"]["healthy"]=False
        with self.assertRaises(MonitorBlocked):require_monitor_health(s,NOW)
    def test_stale(self):
        s=sample();s["database"]["observed_at"]=(NOW-timedelta(seconds=91)).isoformat()
        self.assertFalse(evaluate_health(s,NOW)["healthy"])
    def test_future(self):
        s=sample();s["clock"]["observed_at"]=(NOW+timedelta(seconds=1)).isoformat()
        self.assertFalse(evaluate_health(s,NOW)["healthy"])
    def test_naive_time(self):
        s=sample();s["broker"]["observed_at"]="2026-11-18T15:00:00"
        self.assertFalse(evaluate_health(s,NOW)["healthy"])
    def test_invalid_time(self):
        s=sample();s["broker"]["observed_at"]="not-a-date"
        self.assertFalse(evaluate_health(s,NOW)["healthy"])
    def test_age_limit(self):
        with self.assertRaises(MonitorBlocked):evaluate_health(sample(),NOW,max_age_seconds=0)
    def test_untrusted_true(self):
        s=sample();s["broker"]["healthy"]=1
        self.assertFalse(evaluate_health(s,NOW)["healthy"])
    def test_no_heartbeats(self):
        self.assertEqual(len(evaluate_health({},NOW)["problems"]),len(REQUIRED))
if __name__=="__main__":unittest.main()
