import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from intraday_calendar import session_window, verify_clock, CalendarBlocked

NY = ZoneInfo("America/New_York")
DAY = {"date": "2026-11-18", "open": "09:30", "close": "16:00"}
EARLY = {"date": "2026-11-18", "open": "09:30", "close": "13:00"}

def at(hour, minute=0):
    return datetime(2026, 11, 18, hour, minute, tzinfo=NY)

class CalendarTests(unittest.TestCase):
    def test_regular_entry_window(self):
        self.assertTrue(session_window(DAY, at(10))["entry_allowed"])
    def test_preopen_blocks(self):
        self.assertFalse(session_window(DAY, at(9))["entry_allowed"])
    def test_early_close_stops_entries(self):
        self.assertFalse(session_window(EARLY, at(12, 20))["entry_allowed"])
    def test_early_close_flatten_due(self):
        self.assertTrue(session_window(EARLY, at(12, 35))["flatten_due"])
    def test_regular_close_flatten_due(self):
        self.assertTrue(session_window(DAY, at(15, 40))["flatten_due"])
    def test_past_close(self):
        self.assertTrue(session_window(EARLY, at(13))["past_close"])
    def test_wrong_calendar_date_blocks(self):
        with self.assertRaises(CalendarBlocked):
            session_window({**DAY, "date": "2026-11-19"}, at(10))
    def test_naive_clock_blocks(self):
        with self.assertRaises(CalendarBlocked):
            session_window(DAY, datetime(2026, 11, 18, 10))
    def test_invalid_hours_blocks(self):
        with self.assertRaises(CalendarBlocked):
            session_window({**DAY, "close": "08:00"}, at(10))
    def test_clock_agreement(self):
        self.assertTrue(verify_clock(DAY, {"is_open": True}, at(10))["entry_allowed"])
    def test_clock_disagreement_blocks(self):
        with self.assertRaises(CalendarBlocked):
            verify_clock(DAY, {"is_open": False}, at(10))
    def test_missing_clock_blocks(self):
        with self.assertRaises(CalendarBlocked):
            verify_clock(DAY, {}, at(10))

if __name__ == "__main__":
    unittest.main()
