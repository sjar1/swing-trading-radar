import unittest
from datetime import date
from intraday_recovery_readiness import inspect_recovery
from intraday_durable_fill_reconciliation import DurableFillBlocked
D=date(2026,11,18)
I=[("intraday-a","SPY","broker-1")]
O=[{"id":"broker-1","client_order_id":"intraday-a","symbol":"SPY"}]
def broker(base,path):
    if path=="/v2/account":return {"id":"paper-id"}
    if "status=open" in path:return O
    if path=="/v2/positions":return []
    raise AssertionError("unexpected broker endpoint")
class RecoveryReadinessTests(unittest.TestCase):
    def run_probe(self,api_fn=broker,load_fn=lambda *a:I):
        return inspect_recovery(db_url="opaque",session_date=D,api_fn=api_fn,
            base="PAPER",expected_account_id="paper-id",load_fn=load_fn)
    def test_consistent_state_still_blocks_restart(self):
        x=self.run_probe()
        self.assertEqual(x["open_order_count"],1)
        self.assertFalse(x["restart_clear"])
        self.assertFalse(x["execution_enabled"])
        self.assertIn("open_orders_require_reconciliation",x["blockers"])
    def test_empty_state_still_blocks_without_history(self):
        def empty(base,path):
            if path=="/v2/account":return {"id":"paper-id"}
            return []
        x=self.run_probe(api_fn=empty,load_fn=lambda *a:[])
        self.assertIn("history_not_certified",x["blockers"])
        self.assertFalse(x["restart_clear"])
    def test_unknown_order_fails(self):
        with self.assertRaises(DurableFillBlocked):self.run_probe(load_fn=lambda *a:[])
    def test_identity_mismatch_prevents_database_read(self):
        def fail(*args):raise AssertionError("database should not be read")
        with self.assertRaises(Exception):
            inspect_recovery(db_url="opaque",session_date=D,api_fn=broker,
                base="PAPER",expected_account_id="wrong",load_fn=fail)
    def test_invalid_date_fails(self):
        with self.assertRaises(ValueError):
            inspect_recovery(db_url="opaque",session_date="2026-11-18",api_fn=broker,
                base="PAPER",expected_account_id="paper-id",load_fn=lambda *a:I)
if __name__=="__main__":unittest.main()
