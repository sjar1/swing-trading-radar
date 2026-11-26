import unittest
from unittest.mock import patch
import intraday_backfill_diagnostic as d
class BackfillDiagnosticTests(unittest.TestCase):
    def test_broker_write_rejected(self):
        with self.assertRaises(ValueError):
            d.read_only_api(d.PAPER,"/v2/orders",method="POST",payload={})
    def test_live_broker_rejected(self):
        with self.assertRaises(ValueError):
            d.read_only_api("https://api.alpaca.markets","/v2/orders")
    def test_missing_credentials(self):
        with patch.dict(d.os.environ,{},clear=True):
            self.assertEqual(d.main(),2)
    def test_invalid_hours_fail_closed(self):
        with patch.dict(d.os.environ,{"ALPACA_INTRADAY_API_KEY":"x",
            "ALPACA_INTRADAY_API_SECRET":"y","INTRADAY_BACKFILL_HOURS":"999"}):
            self.assertEqual(d.main(),3)
if __name__=="__main__":unittest.main()
