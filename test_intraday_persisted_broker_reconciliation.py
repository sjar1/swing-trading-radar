import sqlite3,unittest
from intraday_persistent_recovery_simulator import initialize,persist_event,PersistenceBlocked
from intraday_persisted_broker_reconciliation import reconcile
from intraday_broker_recovery import RecoveryBlocked
ID="intraday-test"
def event(n,t,**kw):return {"event_id":str(n),"client_order_id":ID,"type":t,**kw}
def broker(**kw):return {"id":"broker-1","client_order_id":ID,"status":"new","filled_qty":"0"} | kw
class BrokerJournalTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        initialize(self.db)
    def tearDown(self):self.db.close()
    def put(self,*events):
        for x in events:persist_event(self.db,x)
    def check(self,order):
        x=reconcile(conn=self.db,client_order_id=ID,broker_order=order)
        self.assertFalse(x["retry_submission"])
        self.assertFalse(x["restart_clear"])
        self.assertFalse(x["execution_enabled"])
        self.assertEqual(x["broker_writes"],0)
        return x
    def test_timeout_and_missing_broker_never_retry(self):
        self.put(event(1,"submission_attempted"),event(2,"submission_timeout"))
        self.assertEqual(self.check(None)["status"],"unresolved_broker_order")
    def test_ambiguous_submission_found_by_client_id(self):
        self.put(event(1,"submission_attempted"))
        self.assertEqual(self.check(broker())["status"],"broker_identity_observed")
    def test_acknowledged_broker_identity_matches(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"))
        self.assertEqual(self.check(broker())["persisted_phase"],"acknowledged")
    def test_acknowledged_broker_identity_mismatch(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"))
        with self.assertRaises(PersistenceBlocked):self.check(broker(id="other"))
    def test_partial_fill_remains_uncertified(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"),
                 event(3,"partially_filled",broker_order_id="broker-1",fill_qty="0.5"))
        x=self.check(broker(status="partially_filled",filled_qty="0.5"))
        self.assertEqual(x["persisted_fill_quantity"],"0.5")
        self.assertFalse(x["fill_history_certified"])
    def test_wrong_client_rejected(self):
        self.put(event(1,"submission_attempted"))
        with self.assertRaises(RecoveryBlocked):self.check(broker(client_order_id="other"))
    def test_reserved_without_submission_blocks(self):
        with self.assertRaises(PersistenceBlocked):self.check(None)
    def test_unknown_broker_status_stays_blocked(self):
        self.put(event(1,"submission_attempted"))
        self.assertEqual(self.check(broker(status="pending_replace"))["status"],"unresolved_broker_order")
    def test_broker_filled_but_journal_only_acknowledged(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"))
        with self.assertRaises(PersistenceBlocked):self.check(broker(status="filled"))
    def test_partial_fill_broker_regression(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"),
                 event(3,"partially_filled",broker_order_id="broker-1",fill_qty="0.5"))
        with self.assertRaises(PersistenceBlocked):self.check(broker(status="new"))
    def test_partial_fill_broker_terminal_requires_event(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"),
                 event(3,"partially_filled",broker_order_id="broker-1",fill_qty="0.5"))
        with self.assertRaises(PersistenceBlocked):self.check(broker(status="filled"))
    def test_terminal_journal_broker_conflict(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"),
                 event(3,"filled",broker_order_id="broker-1",fill_qty="1"))
        with self.assertRaises(PersistenceBlocked):self.check(broker(status="canceled"))
    def test_broker_fill_quantity_mismatch_blocks(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"),
                 event(3,"partially_filled",broker_order_id="broker-1",fill_qty="0.5"))
        with self.assertRaises(PersistenceBlocked):
            self.check(broker(status="partially_filled",filled_qty="0.75"))
    def test_missing_broker_fill_quantity_blocks(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"))
        with self.assertRaises(PersistenceBlocked):
            self.check({"id":"broker-1","client_order_id":ID,"status":"new"})
    def test_nonfinite_broker_fill_quantity_blocks(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"))
        with self.assertRaises(PersistenceBlocked):
            self.check(broker(filled_qty="NaN"))
    def test_matching_decimal_quantities_observed_only(self):
        self.put(event(1,"submission_attempted"),event(2,"acknowledged",broker_order_id="broker-1"),
                 event(3,"partially_filled",broker_order_id="broker-1",fill_qty="0.5"))
        x=self.check(broker(status="partially_filled",filled_qty="0.500"))
        self.assertTrue(x["fill_quantity_equal"])
        self.assertFalse(x["fill_history_certified"])
if __name__=="__main__":unittest.main()
