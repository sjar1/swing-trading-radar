import unittest
from intraday_snapshot_consistency import verify_snapshots
from intraday_durable_fill_reconciliation import DurableFillBlocked
def row(client="intraday-one",symbol="SPY",broker="broker-one"):
    return (client,symbol,broker,"accepted",1,broker,"new",None)
class SnapshotTests(unittest.TestCase):
    def test_empty(self):
        self.assertFalse(verify_snapshots(event_rows=[],intents=[])["entry_permitted"])
    def test_match(self):
        x=verify_snapshots(event_rows=[row()],intents=[("intraday-one","SPY","broker-one")])
        self.assertEqual(x["identity_count"],1)
        self.assertFalse(x["restart_clear"])
    def test_same_count_wrong_client(self):
        with self.assertRaises(DurableFillBlocked):
            verify_snapshots(event_rows=[row()],intents=[("intraday-other","SPY","broker-one")])
    def test_same_count_wrong_symbol(self):
        with self.assertRaises(DurableFillBlocked):
            verify_snapshots(event_rows=[row()],intents=[("intraday-one","QQQ","broker-one")])
    def test_same_count_wrong_broker(self):
        with self.assertRaises(DurableFillBlocked):
            verify_snapshots(event_rows=[row()],intents=[("intraday-one","SPY","broker-other")])
    def test_duplicate_intent(self):
        with self.assertRaises(DurableFillBlocked):
            verify_snapshots(event_rows=[row()],intents=[("intraday-one","SPY","broker-one")]*2)
    def test_conflicting_event_identity(self):
        with self.assertRaises(DurableFillBlocked):
            verify_snapshots(event_rows=[row(),row(symbol="QQQ")],intents=[("intraday-one","SPY","broker-one")])
if __name__=="__main__":unittest.main()
