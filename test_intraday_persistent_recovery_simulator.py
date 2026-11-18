import os,sqlite3,tempfile,unittest
from intraday_persistent_recovery_simulator import initialize,persist_event,recover,PersistenceBlocked
from intraday_order_state_replay import ReplayBlocked
ID="intraday-test"
def event(n,kind,**kw):return {"event_id":str(n),"client_order_id":ID,"type":kind,**kw}
S=event(1,"submission_attempted")
A=event(2,"acknowledged",broker_order_id="broker-1")
class PersistentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.tmp.name,"journal.sqlite")
        self.conn=sqlite3.connect(self.path)
        initialize(self.conn)
    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()
    def restart(self):
        self.conn.close()
        self.conn=sqlite3.connect(self.path)
        return recover(self.conn,ID)
    def assert_blocked(self,state):
        self.assertFalse(state["restart_clear"])
        self.assertFalse(state["entry_permitted"])
        self.assertFalse(state["execution_enabled"])
        self.assertEqual(state["broker_writes"],0)
    def test_crash_after_submit_before_ack(self):
        persist_event(self.conn,S)
        x=self.restart()
        self.assertEqual(x["phase"],"submission_unknown")
        self.assertTrue(x["requires_broker_reconciliation"])
        self.assert_blocked(x)
    def test_restart_after_partial_fill(self):
        for x in [S,A,event(3,"partially_filled",broker_order_id="broker-1",fill_qty="0.5")]:
            persist_event(self.conn,x)
        x=self.restart()
        self.assertEqual(x["filled_quantity"],"0.5")
        self.assert_blocked(x)
    def test_restart_after_cancel_with_partial_fill(self):
        for x in [S,A,event(3,"partially_filled",broker_order_id="broker-1",fill_qty="0.5"),event(4,"canceled")]:
            persist_event(self.conn,x)
        x=self.restart()
        self.assertEqual(x["phase"],"canceled")
        self.assertEqual(x["filled_quantity"],"0.5")
        self.assert_blocked(x)
    def test_duplicate_event_rejected(self):
        persist_event(self.conn,S)
        with self.assertRaises(PersistenceBlocked):persist_event(self.conn,S)
    def test_missing_acknowledgement_blocks_broker_order(self):
        persist_event(self.conn,S)
        with self.assertRaises(PersistenceBlocked):
            recover(self.conn,ID,{"client_order_id":ID,"id":"broker-1","status":"new"})
    def test_broker_id_mismatch_blocks(self):
        for x in [S,A]:persist_event(self.conn,x)
        with self.assertRaises(PersistenceBlocked):
            recover(self.conn,ID,{"client_order_id":ID,"id":"other","status":"new"})
    def test_matched_broker_still_not_authorized(self):
        for x in [S,A]:persist_event(self.conn,x)
        x=recover(self.conn,ID,{"client_order_id":ID,"id":"broker-1","status":"new"})
        self.assertTrue(x["broker_order_observed"])
        self.assert_blocked(x)
    def test_corrupt_persisted_event_blocks(self):
        with self.conn:
            self.conn.execute("INSERT INTO simulated_events(event_id,client_order_id,payload) VALUES(?,?,?)",
                              ("bad",ID,"{broken"))
        with self.assertRaises(PersistenceBlocked):self.restart()
    def test_invalid_sequence_blocks(self):
        persist_event(self.conn,A)
        with self.assertRaises(ReplayBlocked):self.restart()
if __name__=="__main__":unittest.main()
