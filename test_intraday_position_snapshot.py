import unittest
from intraday_position_snapshot import inspect_positions
from intraday_alpaca_fills import FillHistoryBlocked

class PositionSnapshotTests(unittest.TestCase):
    def call(self,positions):
        return inspect_positions(api_fn=lambda base,path: positions,base="PAPER")
    def test_empty_snapshot_is_not_certification(self):
        x=self.call([])
        self.assertEqual(x["position_count"],0)
        self.assertFalse(x["position_attribution_certified"])
        self.assertFalse(x["execution_enabled"])
    def test_valid_positions_not_attributed(self):
        x=self.call([{"symbol":"SPY","qty":"2"},{"symbol":"QQQ","qty":"-1.5"}])
        self.assertEqual(x["position_count"],2)
        self.assertFalse(x["position_attribution_certified"])
    def test_malformed_snapshot_blocks(self):
        with self.assertRaises(FillHistoryBlocked):self.call({})
    def test_duplicate_symbol_blocks(self):
        with self.assertRaises(FillHistoryBlocked):self.call([{"symbol":"SPY","qty":"1"},{"symbol":"SPY","qty":"2"}])
    def test_zero_or_nonfinite_quantity_blocks(self):
        for qty in ("0","NaN","Infinity","abc"):
            with self.subTest(qty=qty),self.assertRaises(FillHistoryBlocked):
                self.call([{"symbol":"SPY","qty":qty}])
    def test_network_failure_propagates(self):
        def fail(base,path):raise TimeoutError("private")
        with self.assertRaises(TimeoutError):inspect_positions(api_fn=fail,base="PAPER")
if __name__=="__main__":unittest.main()
