import unittest
from datetime import datetime,timezone
from intraday_reconciliation_evidence import assemble,EvidenceBlocked
from intraday_reconciliation_health import evaluate,ReconciliationHealthBlocked
NOW=datetime(2026,11,18,15,0,tzinfo=timezone.utc)
def snapshot(fills=None):return {"session_history_exhausted":True,"fills":fills if fills is not None else []}
class EvidenceTests(unittest.TestCase):
    def test_empty_session_never_proves_history(self):
        x=assemble(session_snapshot=snapshot(),intents=[],positions=[],observed_at=NOW,broker_snapshot_complete=True)
        self.assertFalse(x["account_history_complete"])
        self.assertFalse(x["position_attribution_certified"])
        with self.assertRaises(ReconciliationHealthBlocked):evaluate(x,now=NOW)
    def test_matching_fill_still_not_full_account(self):
        intents=[("intraday-abc","AAPL","broker1")]
        fills=[{"event_id":"e1","client_order_id":"intraday-abc","symbol":"AAPL","order_id":"broker1"}]
        x=assemble(session_snapshot=snapshot(fills),intents=intents,positions=[{"symbol":"AAPL"}],observed_at=NOW,broker_snapshot_complete=True)
        self.assertEqual(x["matched_fill_count"],1)
        self.assertEqual(x["unattributed_positions"],1)
        self.assertFalse(x["execution_enabled"])
    def test_unowned_fill_rejected(self):
        fills=[{"event_id":"e1","client_order_id":"intraday-abc","symbol":"AAPL","order_id":"broker1"}]
        with self.assertRaises(EvidenceBlocked):assemble(session_snapshot=snapshot(fills),intents=[],positions=[],observed_at=NOW,broker_snapshot_complete=True)
    def test_truncated_history_rejected(self):
        with self.assertRaises(EvidenceBlocked):assemble(session_snapshot={"session_history_exhausted":False,"fills":[]},intents=[],positions=[],observed_at=NOW,broker_snapshot_complete=True)
    def test_missing_broker_proof_rejected(self):
        with self.assertRaises(EvidenceBlocked):assemble(session_snapshot=snapshot(),intents=[],positions=[],observed_at=NOW)
    def test_duplicate_position_rejected(self):
        with self.assertRaises(EvidenceBlocked):assemble(session_snapshot=snapshot(),intents=[],positions=[{"symbol":"AAPL"},{"symbol":"AAPL"}],observed_at=NOW,broker_snapshot_complete=True)
    def test_naive_timestamp_rejected(self):
        with self.assertRaises(EvidenceBlocked):assemble(session_snapshot=snapshot(),intents=[],positions=[],observed_at=NOW.replace(tzinfo=None),broker_snapshot_complete=True)
if __name__=="__main__":unittest.main()
