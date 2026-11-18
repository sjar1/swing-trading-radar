import unittest
from intraday_live_order_probe import inspect_orders
from intraday_durable_fill_reconciliation import DurableFillBlocked
from intraday_broker_recovery import RecoveryBlocked
I=("intraday-one","SPY","broker-one")
def run(intents,reader):
    return inspect_orders(intents=intents,api_fn=reader,base="PAPER")
def broker(*args):
    return {"client_order_id":"intraday-one","id":"broker-one","symbol":"SPY","status":"new"}
class LiveOrderProbeTests(unittest.TestCase):
    def test_empty_snapshot_stays_blocked(self):
        x=run([],broker)
        self.assertEqual(x["matched_broker_orders"],0)
        self.assertFalse(x["restart_clear"])
        self.assertFalse(x["execution_enabled"])
        self.assertEqual(x["broker_writes"],0)
    def test_matching_order(self):
        x=run([I],broker)
        self.assertEqual(x["matched_broker_orders"],1)
        self.assertFalse(x["retry_submission"])
    def test_missing_broker_order_unresolved(self):
        x=run([I],lambda *args:None)
        self.assertEqual(x["unresolved_broker_orders"],1)
        self.assertFalse(x["retry_submission"])
    def test_api_failure_unresolved(self):
        def fail(*args):raise RuntimeError("network down")
        self.assertEqual(run([I],fail)["unresolved_broker_orders"],1)
    def test_wrong_broker_id_blocks(self):
        with self.assertRaises(RecoveryBlocked):
            run([I],lambda *args:{**broker(),"id":"other"})
    def test_wrong_symbol_blocks(self):
        with self.assertRaises(RecoveryBlocked):
            run([I],lambda *args:{**broker(),"symbol":"QQQ"})
    def test_duplicate_intent_blocks(self):
        with self.assertRaises(DurableFillBlocked):run([I,I],broker)
    def test_budget_blocks_before_api(self):
        with self.assertRaises(DurableFillBlocked):
            inspect_orders(intents=[I]*21,api_fn=broker,base="PAPER")
    def test_unknown_broker_status_unresolved(self):
        x=run([I],lambda *args:{**broker(),"status":"pending_replace"})
        self.assertEqual(x["unresolved_broker_orders"],1)
if __name__=="__main__":unittest.main()
