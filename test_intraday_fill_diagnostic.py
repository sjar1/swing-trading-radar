import unittest
from unittest.mock import patch
from intraday_fill_diagnostic import summarize,main
from intraday_alpaca_fills import FillHistoryBlocked
class DiagnosticTests(unittest.TestCase):
    def test_summary_is_non_sensitive(self):
        s=summarize({"session_history_exhausted":True,"fills":[{"client_order_id":"secret"}],"orders_count":1})
        self.assertEqual(s["activity_count"],1)
        self.assertNotIn("secret",str(s))
        self.assertFalse(s["account_history_complete"])
        self.assertFalse(s["execution_enabled"])
    def test_incomplete_blocks(self):
        with self.assertRaises(FillHistoryBlocked):summarize({"session_history_exhausted":False,"fills":[]})
    @patch.dict("os.environ",{},clear=True)
    def test_missing_credentials_fail_closed(self):
        with patch("builtins.print") as output:
            self.assertEqual(main(),2)
        self.assertIn("paper_credentials_missing",output.call_args.args[0])
    @patch.dict("os.environ",{"ALPACA_INTRADAY_API_KEY":"test","ALPACA_INTRADAY_API_SECRET":"test"})
    def test_broker_failure_redacted(self):
        with patch("intraday_fill_diagnostic.collect_session_fills",side_effect=RuntimeError("secret-123")):
            with patch("builtins.print") as output:
                self.assertEqual(main(),3)
        self.assertNotIn("secret-123",output.call_args.args[0])
if __name__=="__main__":unittest.main()
