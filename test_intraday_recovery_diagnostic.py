import unittest,io,os,json
from contextlib import redirect_stdout
from unittest.mock import patch
import intraday_recovery_diagnostic as d
def observed_bundle(result):
    def call(**kwargs):
        kwargs["load_fn"]("opaque","2026-11-18")
        return result
    return call
class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        inventory=patch.object(d,"inspect_session_inventory",return_value={
            "status":"bounded_session_inventory","sessions":[],
            "nonempty_session_count":0,"entry_permitted":False,
            "execution_enabled":False,"broker_writes":0})
        inventory.start()
        self.addCleanup(inventory.stop)
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
            with patch.object(d,"inspect_bundle",side_effect=observed_bundle({"status":"recovery_observed","restart_clear":False,"execution_enabled":False,"broker_writes":0})):
                with patch.object(d,"load_atomic_snapshot",return_value={"intents":[],"event_rows":[],"execution_rows":[],"snapshot_atomic":True}):
                    with patch.object(d,"load_session_intents",return_value=[]):
                        with redirect_stdout(io.StringIO()) as out:self.assertEqual(d.main(),0)
        self.assertIn('"execution_enabled": false',out.getvalue())
        self.assertIn('"durable_event_audit"',out.getvalue())
        self.assertIn('"broker_order_probe"',out.getvalue())
        self.assertIn('"durable_snapshot_consistency"',out.getvalue())
        result=json.loads(out.getvalue())
        self.assertEqual(result["status"],"insufficient_nonempty_recovery_evidence")
        self.assertEqual(result["next_step"],"observe_real_paper_durable_order_intents")
        self.assertFalse(result["entry_permitted"])
    def test_upstream_authorization_claim_cannot_escape_diagnostic(self):
        upstream={"status":"recovery_observed","restart_clear":True,
                  "entry_permitted":True,"execution_enabled":True,
                  "broker_writes":5,"account_history_complete":True,
                  "position_attribution_certified":True}
        with patch.dict(os.environ,{"INTRADAY_DATABASE_URL":"opaque","ALPACA_INTRADAY_API_KEY":"key","ALPACA_INTRADAY_API_SECRET":"secret","ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID":"account"}):
            with patch.object(d,"inspect_bundle",side_effect=observed_bundle(upstream)):
                with patch.object(d,"load_session_intents",return_value=[]):
                    with patch.object(d,"load_atomic_snapshot",return_value={"intents":[],"event_rows":[],"execution_rows":[],"snapshot_atomic":True}):
                        with redirect_stdout(io.StringIO()) as out:self.assertEqual(d.main(),0)
        result=json.loads(out.getvalue())
        for field in ("restart_clear","entry_permitted","execution_enabled","account_history_complete","position_attribution_certified"):
            self.assertIs(result[field],False)
        self.assertEqual(result["broker_writes"],0)
    def test_failed_diagnostic_cannot_report_upstream_authorization(self):
        upstream={"entry_permitted":True,"execution_enabled":True,
                  "broker_writes":2,"restart_clear":True,
                  "account_history_complete":True,
                  "position_attribution_certified":True}
        with patch.dict(os.environ,{"INTRADAY_DATABASE_URL":"opaque","ALPACA_INTRADAY_API_KEY":"key","ALPACA_INTRADAY_API_SECRET":"secret","ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID":"account"}):
            with patch.object(d,"inspect_bundle",return_value=upstream):
                with patch.object(d,"load_atomic_snapshot",side_effect=RuntimeError("private-db-secret")):
                    with redirect_stdout(io.StringIO()) as out:self.assertEqual(d.main(),3)
        result=json.loads(out.getvalue())
        self.assertEqual(result["reason"],"RuntimeError")
        self.assertNotIn("private-db-secret",out.getvalue())
        for field in ("entry_permitted","execution_enabled","restart_clear","account_history_complete","position_attribution_certified"):
            self.assertIs(result[field],False)
        self.assertEqual(result["broker_writes"],0)
    def test_cross_transaction_identity_drift_blocks(self):
        def bundle(**kwargs):
            kwargs["load_fn"]("opaque","2026-11-18")
            return {"execution_enabled":False,"broker_writes":0}
        with patch.dict(os.environ,{"INTRADAY_DATABASE_URL":"opaque","ALPACA_INTRADAY_API_KEY":"key","ALPACA_INTRADAY_API_SECRET":"secret","ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID":"account"}):
            with patch.object(d,"inspect_bundle",side_effect=bundle):
                with patch.object(d,"load_session_intents",return_value=[("intraday-a","QQQ",None)]):
                    with patch.object(d,"load_atomic_snapshot",return_value={"intents":[("intraday-a","SPY",None)],"event_rows":[],"execution_rows":[],"snapshot_atomic":True}):
                        with redirect_stdout(io.StringIO()) as out:self.assertEqual(d.main(),3)
        self.assertIn("ValueError",out.getvalue())
        self.assertIn('"entry_permitted": false',out.getvalue())
    def test_cross_snapshot_intent_count_mismatch_blocks(self):
        with patch.dict(os.environ,{"INTRADAY_DATABASE_URL":"opaque","ALPACA_INTRADAY_API_KEY":"key","ALPACA_INTRADAY_API_SECRET":"secret","ALPACA_INTRADAY_EXPECTED_ACCOUNT_ID":"account"}):
            with patch.object(d,"inspect_bundle",return_value={"execution_enabled":False}):
                with patch.object(d,"load_atomic_snapshot",return_value={"intents":[("intraday-a","SPY",None)],"event_rows":[],"execution_rows":[],"snapshot_atomic":True}):
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
