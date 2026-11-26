import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from intraday_engine import main

class ScannerCalendarIntegrationTests(unittest.TestCase):
    def run_scanner(self, calendar):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "result.json"
            def fake_api(base, path, method="GET", payload=None):
                if path == "/v2/clock":
                    return {"is_open": False}
                if path.startswith("/v2/calendar?"):
                    return calendar
                raise AssertionError("Scanner must not query account or bars when calendar is unavailable")
            with patch.dict(os.environ, {"ALPACA_INTRADAY_API_KEY": "dummy",
                                        "ALPACA_INTRADAY_API_SECRET": "dummy"}):
                with patch("intraday_engine.OUT", output), patch("intraday_engine.api", side_effect=fake_api):
                    main()
            return json.loads(output.read_text())

    def test_missing_calendar_blocks_before_account_access(self):
        result = self.run_scanner([])
        self.assertEqual(result["status"], "calendar_unavailable")
        self.assertEqual(result["orders_submitted"], 0)

    def test_multiple_calendar_sessions_block(self):
        result = self.run_scanner([{}, {}])
        self.assertEqual(result["status"], "calendar_unavailable")

    def test_wrong_calendar_date_blocks(self):
        result = self.run_scanner([{"date": "2000-01-01", "open": "09:30", "close": "16:00"}])
        self.assertEqual(result["status"], "calendar_unverified")

if __name__ == "__main__":
    unittest.main()
