import unittest,io,os
from contextlib import redirect_stdout
from unittest.mock import patch
import intraday_recovery_diagnostic as d
class DiagnosticTests(unittest.TestCase):
    def test_missing_credentials_block(self):
        with patch.dict(os.environ,{"INTRADAY_DATABASE_URL":"opaque","ALPACA_INTRADAY_API_KEY":"","ALPACA_INTRADAY_API_SECRET":"","ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID":""}):
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(d.main(),2)
        self.assertIn("missing_paper_identity_or_credentials",out.getvalue())
    def test_sanitized_failure(self):
        with patch.dict(os.environ,{"INTRADAY_DATABASE_URL":"secret-db","ALPACA_INTRADAY_API_KEY":"key","ALPACA_INTRADAY_API_SECRET":"secret","ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID":"private-account"}):
            with patch.object(d,"inspect_bundle",side_effect=RuntimeError("secret-db private-account")):
                with redirect_stdout(io.StringIO()) as out:self.assertEqual(d.main(),3)
        self.assertNotIn("secret-db",out.getvalue())
        self.assertNotIn("private-account",out.getvalue())
    def test_success_is_still_read_only(self):
        with patch.dict(os.environ,{"INTRADAY_DATABASE_URL":"opaque","ALPACA_INTRADAY_API_KEY":"key","ALPACA_INTRADAY_API_SECRET":"secret","ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID":"private-account"}):
            with patch.object(d,"inspect_bundle",return_value={"status":"recovery_observed","restart_clear":False,"execution_enabled":False,"broker_writes":0}):
                with patch.object(d,"load_atomic_snapshot",return_value={"intents":[],"event_rows":[],"execution_rows":[],"snapshot_atomic":True}):
                    with patch.object(d,"load_session_intents",return_value=[]):
                        with redirect_stdout(io.StringIO()) as out:self.assertEqual(d.main(),0)
        self.assertIn('"execution_enabled": false',out.getvalue())
        self.assertIn('"durable_event_audit"',out.getvalue())
        self.assertIn('"broker_order_probe"',out.getvalue())
        self.assertIn('"durable_snapshot_consistency"',out.getvalue())
    def test_cross_snapshot_intent_count_mismatch_blocks(self):
        with patch.dict(os.environ,{"INTRADAY_DATABASE_URL":"opaque","ALPACA_INTRADAY_API_KEY":"key","ALPACA_INTRADAY_API_SECRET":"secret","ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID":"account"}):
            with patch.object(d,"inspect_bundle",return_value={"execution_enabled":False}):
                with patch.object(d,"load_order_event_rows",return_value=[]):
                    with patch.object(d,"load_session_intents",return_value=[("intraday-a","SPY",None)]):
                        with patch.object(d,"inspect_orders",return_value={"durable_intent_count":1}):
                            with redirect_stdout(io.StringIO()) as out:self.assertEqual(d.main(),3)
        self.assertIn("ValueError",out.getvalue())
    def test_read_only_api_rejects_writes(self):
        with self.assertRaises(ValueError):
            d.read_only_api(d.PAPER,"/v2/orders",method="POST",payload={})
        with self.assertRaises(ValueError):
            d.read_only_api("https://api.alpaca.markets","/v2/account")
if __name__=="__main__":unittest.main()
