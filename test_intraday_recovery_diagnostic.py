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
            with patch.object(d,"inspect_recovery",side_effect=RuntimeError("secret-db private-account")):
                with redirect_stdout(io.StringIO()) as out:self.assertEqual(d.main(),3)
        self.assertNotIn("secret-db",out.getvalue())
        self.assertNotIn("private-account",out.getvalue())
    def test_success_is_still_read_only(self):
        with patch.dict(os.environ,{"INTRADAY_DATABASE_URL":"opaque","ALPACA_INTRADAY_API_KEY":"key","ALPACA_INTRADAY_API_SECRET":"secret","ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID":"private-account"}):
            with patch.object(d,"inspect_recovery",return_value={"status":"recovery_observed","restart_clear":False,"execution_enabled":False,"broker_writes":0}):
                with redirect_stdout(io.StringIO()) as out:self.assertEqual(d.main(),0)
        self.assertIn('"execution_enabled": false',out.getvalue())
if __name__=="__main__":unittest.main()
