import unittest
from datetime import datetime,timezone,timedelta
from intraday_recovery_journal import RecoveryJournal
from intraday_recovery_checkpoint_db import make_checkpoint
from intraday_recovery_restart_gate import restart_observation,RestartBlocked
NOW=datetime(2026,11,18,15,0,tzinfo=timezone.utc)
P=make_checkpoint("2026-11-18",RecoveryJournal())
def obs(at):
    return {"sequence":1,"observed_at":at.isoformat(),"snapshot_complete":True,
            "ownership_verified":True,"open_order_ids":[],"positions":{}}
class RestartTests(unittest.TestCase):
    def test_fresh_broker_snapshot_only_simulates(self):
        out=restart_observation(P,session_date="2026-11-18",
            checkpoint_observed_at=NOW-timedelta(seconds=5),now=NOW,broker_observation=obs(NOW))
        self.assertEqual(out["phase"],"flat")
        self.assertFalse(out["execution_enabled"])
    def test_stale_broker(self):
        with self.assertRaises(RestartBlocked):restart_observation(P,session_date="2026-11-18",
            checkpoint_observed_at=NOW-timedelta(seconds=50),now=NOW,broker_observation=obs(NOW-timedelta(seconds=40)))
    def test_replayed_broker(self):
        with self.assertRaises(RestartBlocked):restart_observation(P,session_date="2026-11-18",
            checkpoint_observed_at=NOW,now=NOW,broker_observation=obs(NOW))
    def test_wrong_session(self):
        with self.assertRaises(RestartBlocked):restart_observation(P,session_date="2026-11-17",
            checkpoint_observed_at=NOW-timedelta(seconds=5),now=NOW,broker_observation=obs(NOW))
    def test_incomplete(self):
        x=obs(NOW);x["ownership_verified"]=False
        with self.assertRaises(RestartBlocked):restart_observation(P,session_date="2026-11-18",
            checkpoint_observed_at=NOW-timedelta(seconds=5),now=NOW,broker_observation=x)
if __name__=="__main__":unittest.main()
