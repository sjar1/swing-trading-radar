import unittest
from intraday_fault_injection import run_scenarios
class FaultInjectionTests(unittest.TestCase):
    def test_all_scenarios(self):
        r=run_scenarios()
        self.assertEqual(r["passed"],r["total"],r["scenarios"])
        self.assertGreaterEqual(r["total"],6)
    def test_never_enables_execution(self):
        r=run_scenarios()
        self.assertFalse(r["execution_enabled"])
        self.assertEqual(r["orders_submitted"],0)
    def test_expected_failure_modes(self):
        names={s["name"] for s in run_scenarios()["scenarios"]}
        self.assertIn("Crash after intent reservation",names)
        self.assertIn("Loss threshold and sticky block",names)
if __name__=="__main__": unittest.main()
