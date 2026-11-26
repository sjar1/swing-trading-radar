import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from intraday_alpaca_fills import normalize,collect_session_fills,FillHistoryBlocked
ORDER={"id":"order-1","client_order_id":"intraday-a","symbol":"AAPL"}
ACT={"id":"activity-1","order_id":"order-1","activity_type":"FILL","symbol":"AAPL","side":"buy","qty":"1","transaction_time":"2026-11-18T15:00:00Z"}
class AlpacaFillsTests(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(normalize([ACT],[ORDER])[0]["client_order_id"],"intraday-a")
    def test_unknown_order_blocks(self):
        with self.assertRaises(FillHistoryBlocked):normalize([ACT],[])
    def test_duplicate_fill_blocks(self):
        with self.assertRaises(FillHistoryBlocked):normalize([ACT,ACT],[ORDER])
    def test_mismatched_symbol_blocks(self):
        with self.assertRaises(FillHistoryBlocked):normalize([{**ACT,"symbol":"MSFT"}],[ORDER])
    def test_invalid_activity_type_blocks(self):
        with self.assertRaises(FillHistoryBlocked):normalize([{**ACT,"activity_type":"DIV"}],[ORDER])
    def test_read_only_calls(self):
        with patch("intraday_alpaca_fills.api",side_effect=[[ORDER],[ACT]] ) as api:
            out=collect_session_fills(datetime(2026,11,18,tzinfo=timezone.utc))
        self.assertEqual(api.call_count,2)
        self.assertTrue(all(call.args[0]=="https://paper-api.alpaca.markets" for call in api.call_args_list))
        self.assertFalse(out["account_history_complete"])
        self.assertFalse(out["execution_enabled"])
        self.assertEqual(out["broker_writes"],0)
    def test_truncated_orders_block(self):
        with patch("intraday_alpaca_fills.api",return_value=[ORDER]*500):
            with self.assertRaises(FillHistoryBlocked):collect_session_fills(datetime(2026,11,18,tzinfo=timezone.utc))
    def test_page_limit_blocks(self):
        with patch("intraday_alpaca_fills.api",side_effect=[[ORDER],[{**ACT,"id":str(i)} for i in range(100)]]):
            with self.assertRaises(FillHistoryBlocked):collect_session_fills(datetime(2026,11,18,tzinfo=timezone.utc),max_pages=1)
if __name__=="__main__":unittest.main()
