import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from intraday_equity_state import initial_state, update_equity_state, EquityStateBlocked

DAY="2026-11-18"
T=datetime(2026,11,18,9,30,tzinfo=ZoneInfo("America/New_York"))

class EquityStateTests(unittest.TestCase):
    def start(self):
        return initial_state(DAY,5000,T)
    def test_bootstrap_flat(self):
        self.assertEqual(self.start()["peak_equity"],5000)
    def test_peak_tracks_gain(self):
        s=update_equity_state(self.start(),DAY,5100,5000,T+timedelta(minutes=1))
        self.assertEqual(s["peak_equity"],5100)
        self.assertFalse(s["blocked"])
    def test_drawdown_from_peak(self):
        s=update_equity_state(self.start(),DAY,5100,5000,T+timedelta(minutes=1))
        s=update_equity_state(s,DAY,5000,5000,T+timedelta(minutes=2))
        self.assertTrue(s["blocked"])
        self.assertEqual(s["drawdown"],100)
    def test_prior_close_loss(self):
        s=update_equity_state(self.start(),DAY,4899,5000,T+timedelta(minutes=1))
        self.assertTrue(s["blocked"])
    def test_missing_state_fails_closed(self):
        with self.assertRaises(EquityStateBlocked):
            update_equity_state(None,DAY,5000,5000,T)
    def test_cross_session_state_fails_closed(self):
        with self.assertRaises(EquityStateBlocked):
            update_equity_state(self.start(),"2026-11-19",5000,5000,T)
    def test_prior_close_change_fails_closed(self):
        with self.assertRaises(EquityStateBlocked):
            update_equity_state(self.start(),DAY,5000,4990,T)
    def test_out_of_order_fails_closed(self):
        with self.assertRaises(EquityStateBlocked):
            update_equity_state(self.start(),DAY,5000,5000,T-timedelta(minutes=1))
    def test_nan_fails_closed(self):
        with self.assertRaises(EquityStateBlocked):
            update_equity_state(self.start(),DAY,float("nan"),5000,T)
    def test_negative_equity_fails_closed(self):
        with self.assertRaises(EquityStateBlocked):
            update_equity_state(self.start(),DAY,-1,5000,T)
    def test_naive_timestamp_fails_closed(self):
        with self.assertRaises(EquityStateBlocked):
            update_equity_state(self.start(),DAY,5000,5000,datetime(2026,11,18))
    def test_bootstrap_wrong_day_fails_closed(self):
        with self.assertRaises(EquityStateBlocked):
            initial_state("2026-11-19",5000,T)

if __name__=="__main__":
    unittest.main()
