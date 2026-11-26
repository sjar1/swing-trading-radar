import unittest
from intraday_recovery_journal import RecoveryJournal,RecoveryJournalBlocked,advance,checkpoint,restore
def obs(n,orders=None,positions=None):
    return {"sequence":n,"snapshot_complete":True,"ownership_verified":True,
            "open_order_ids":orders if orders is not None else [],
            "positions":positions if positions is not None else {}}
class JournalTests(unittest.TestCase):
    def test_replay(self):
        a=advance(RecoveryJournal(),obs(1,["o1"],{"AAPL":2}))
        self.assertEqual(advance(a,obs(1,["o1"],{"AAPL":2})),a)
    def test_conflicting_replay(self):
        a=advance(RecoveryJournal(),obs(1,["o1"]))
        with self.assertRaises(RecoveryJournalBlocked):advance(a,obs(1,[]))
    def test_gap(self):
        with self.assertRaises(RecoveryJournalBlocked):advance(RecoveryJournal(),obs(2))
    def test_restart(self):
        a=advance(RecoveryJournal(),obs(1,["o1"],{"AAPL":2}))
        b=restore(checkpoint(a))
        c=advance(b,obs(2,[],{"AAPL":2}))
        self.assertEqual(c.phase,"await_flat_ack")
        self.assertTrue(advance(c,obs(3)).flat_confirmed)
    def test_reappearing_order(self):
        a=advance(RecoveryJournal(),obs(1,[],{"AAPL":2}))
        with self.assertRaises(RecoveryJournalBlocked):advance(a,obs(2,["o2"],{"AAPL":2}))
    def test_flat_regression(self):
        a=advance(RecoveryJournal(),obs(1))
        with self.assertRaises(RecoveryJournalBlocked):advance(a,obs(2,[],{"AAPL":1}))
    def test_unverified(self):
        x=obs(1);x["ownership_verified"]=False
        with self.assertRaises(RecoveryJournalBlocked):advance(RecoveryJournal(),x)
    def test_checkpoint_tampering(self):
        x=checkpoint(RecoveryJournal());x["flat_confirmed"]=True
        with self.assertRaises(RecoveryJournalBlocked):restore(x)
    def test_negative_qty(self):
        with self.assertRaises(RecoveryJournalBlocked):advance(RecoveryJournal(),obs(1,[],{"AAPL":-1}))
    def test_no_execution(self):
        self.assertFalse(checkpoint(RecoveryJournal())["execution_enabled"])
if __name__=="__main__":unittest.main()
