import unittest
from datetime import datetime,timezone,timedelta
from intraday_integrated_reconciliation import assess
from intraday_reconciliation_evidence import EvidenceBlocked
T=datetime(2026,11,18,tzinfo=timezone.utc)
W=lambda a,b:{"window_start":(T+timedelta(hours=a)).isoformat(),
              "window_end":(T+timedelta(hours=b)).isoformat(),"window_exhausted":True}
class IntegratedReconciliationTests(unittest.TestCase):
    def run_assessment(self,windows=None,positions=None,snapshot=None):
        return assess(windows=[W(0,1)] if windows is None else windows,
            required_start=T,required_end=T+timedelta(hours=1),
            session_snapshot={"session_history_exhausted":True,"fills":[]} if snapshot is None else snapshot,
            intents=[],positions=[] if positions is None else positions,observed_at=T,
            account_verified=True,open_order_count=0,broker_snapshot_complete=True)
    def test_covered_empty_session_still_blocked(self):
        x=self.run_assessment()
        self.assertTrue(x["requested_window_covered"])
        self.assertFalse(x["restart_clear"])
        self.assertFalse(x["execution_enabled"])
        self.assertIn("history_not_certified",x["blockers"])
    def test_gap_detected(self):
        x=self.run_assessment(windows=[W(0,0.5)])
        self.assertIn("history_window_gap",x["blockers"])
    def test_position_blocks(self):
        x=self.run_assessment(positions=[{"symbol":"SPY"}])
        self.assertIn("positions_unattributed",x["blockers"])
    def test_unverified_session_blocks(self):
        with self.assertRaises(EvidenceBlocked):
            self.run_assessment(snapshot={"session_history_exhausted":False,"fills":[]})
    def test_broker_snapshot_required(self):
        with self.assertRaises(EvidenceBlocked):
            assess(windows=[W(0,1)],required_start=T,required_end=T+timedelta(hours=1),
                session_snapshot={"session_history_exhausted":True,"fills":[]},intents=[],
                positions=[],observed_at=T,account_verified=True,open_order_count=0)
if __name__=="__main__":unittest.main()
