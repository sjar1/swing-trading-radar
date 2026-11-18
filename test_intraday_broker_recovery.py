import unittest
from unittest.mock import patch
from intraday_broker_recovery import decide,inspect,RecoveryBlocked
ID="intraday-test-1"
class RecoveryTests(unittest.TestCase):
    def test_missing_order_never_retry(self):
        r=decide(ID,"unknown",None);self.assertFalse(r["retry_submission"]);self.assertFalse(r["reconciled"])
    def test_broker_ack(self):
        r=decide(ID,"unknown",{"client_order_id":ID,"id":"b1","status":"accepted"})
        self.assertEqual(r["suggested_state"],"accepted")
    def test_filled(self):
        self.assertEqual(decide(ID,"unknown",{"client_order_id":ID,"id":"b1","status":"filled"})["suggested_state"],"filled")
    def test_wrong_id(self):
        with self.assertRaises(RecoveryBlocked):decide(ID,"unknown",{"client_order_id":"wrong","id":"b1","status":"filled"})
    def test_pending_is_ambiguous(self):
        self.assertFalse(decide(ID,"unknown",{"client_order_id":ID,"id":"b1","status":"pending_cancel"})["reconciled"])
    def test_network_error_never_retry(self):
        with patch("intraday_broker_recovery.api",side_effect=TimeoutError):
            self.assertFalse(inspect(ID,"unknown")["retry_submission"])
    def test_no_broker_post(self):
        with patch("intraday_broker_recovery.api",return_value={"client_order_id":ID,"id":"b1","status":"accepted"}) as call:
            inspect(ID,"unknown")
            self.assertEqual(call.call_args.args[0],"https://paper-api.alpaca.markets")
            self.assertEqual(len(call.call_args.args),2)
    def test_invalid_state(self):
        with self.assertRaises(RecoveryBlocked):inspect(ID,"reserved")
if __name__=="__main__":unittest.main()
