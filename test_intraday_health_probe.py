import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from intraday_health_probe import probe,main
NOW=datetime(2026,11,18,15,0,tzinfo=timezone.utc)
class Cursor:
    def execute(self,*args):pass
    def fetchall(self):return []
    def __enter__(self):return self
    def __exit__(self,*args):pass
class Conn:
    def cursor(self):return Cursor()
    def __enter__(self):return self
    def __exit__(self,*args):pass
def api(base,path):
    if path=="/v2/account":return {"status":"ACTIVE","trading_blocked":False,"account_blocked":False}
    if path=="/v2/positions":return []
    if path=="/v2/orders?status=open&limit=500":return []
    if path=="/v2/clock":return {"is_open":True,"timestamp":"2026-11-18T15:00:00Z"}
    raise AssertionError("unexpected_api")
class ProbeTests(unittest.TestCase):
    @patch.dict("os.environ",{"INTRADAY_DATABASE_URL":"test"})
    def test_healthy_connections_still_block_execution(self):
        out=probe(api_fn=api,connect_fn=lambda *a,**kw:Conn(),now_fn=lambda:NOW)
        self.assertEqual(len(out["observed_components"]),4)
        self.assertFalse(out["monitor_fully_healthy"])
        self.assertFalse(out["execution_enabled"])
        self.assertIn("reconciliation_not_observed",out["problems"])
    @patch.dict("os.environ",{"INTRADAY_DATABASE_URL":"test"})
    def test_broker_failure_is_redacted(self):
        def fail(base,path):raise RuntimeError("secret")
        out=probe(api_fn=fail,connect_fn=lambda *a,**kw:Conn(),now_fn=lambda:NOW)
        self.assertNotIn("secret",str(out))
        self.assertIn("broker_unavailable",out["problems"])
    @patch.dict("os.environ",{},clear=True)
    def test_database_failure_blocks(self):
        out=probe(api_fn=api,connect_fn=lambda *a,**kw:Conn(),now_fn=lambda:NOW)
        self.assertIn("database_unavailable",out["problems"])
    def test_invalid_clock(self):
        def bad(base,path):
            return {} if path=="/v2/clock" else api(base,path)
        out=probe(api_fn=bad,connect_fn=lambda *a,**kw:Conn(),now_fn=lambda:NOW)
        self.assertIn("clock_unavailable",out["problems"])
    def test_main_redacts_exception(self):
        with patch("intraday_health_probe.probe",side_effect=RuntimeError("secret-123")):
            with patch("builtins.print") as output:
                self.assertEqual(main(),3)
        self.assertNotIn("secret-123",output.call_args.args[0])
if __name__=="__main__":unittest.main()
