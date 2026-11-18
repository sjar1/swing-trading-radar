import unittest
from datetime import datetime,timezone
from intraday_durable_event_audit import audit_rows
from intraday_durable_fill_reconciliation import DurableFillBlocked
T=datetime(2026,11,18,tzinfo=timezone.utc)
def row(**kw):
    x=["intraday-1","SPY","broker-1","accepted",1,"broker-1","accepted",T]
    for k,v in kw.items():x[{"client":0,"symbol":1,"broker":2,"state":3,
                              "event_id":4,"event_broker":5,"status":6,"stamp":7}[k]]=v
    return tuple(x)
class AuditTests(unittest.TestCase):
    def test_consistent_event(self):
        x=audit_rows([row()])
        self.assertEqual(x["event_count"],1)
        self.assertFalse(x["restart_clear"])
        self.assertFalse(x["execution_enabled"])
        self.assertEqual(x["broker_writes"],0)
    def test_empty_snapshot_never_certifies_history(self):
        x=audit_rows([])
        self.assertFalse(x["broker_history_exhaustive"])
        self.assertFalse(x["entry_permitted"])
    def test_left_join_without_events(self):
        x=audit_rows([row(state="reserved",broker=None,event_id=None,
                          event_broker=None,status=None,stamp=None)])
        self.assertEqual(x["orders_without_events"],1)
    def test_ambiguous_order(self):
        self.assertEqual(audit_rows([row(state="partially_filled")])["ambiguous_order_count"],1)
    def test_duplicate_event_rejected(self):
        with self.assertRaises(DurableFillBlocked):audit_rows([row(),row()])
    def test_broker_identity_mismatch(self):
        with self.assertRaises(DurableFillBlocked):audit_rows([row(event_broker="other")])
    def test_conflicting_intent_state(self):
        with self.assertRaises(DurableFillBlocked):audit_rows([row(),row(state="filled",event_id=2)])
    def test_invalid_event_timestamp(self):
        with self.assertRaises(DurableFillBlocked):audit_rows([row(stamp=T.replace(tzinfo=None))])
    def test_partial_event_record(self):
        with self.assertRaises(DurableFillBlocked):audit_rows([row(event_id=None)])
    def test_bad_order_state(self):
        with self.assertRaises(DurableFillBlocked):audit_rows([row(state="impossible")])
if __name__=="__main__":unittest.main()
