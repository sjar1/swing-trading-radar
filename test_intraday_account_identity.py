import unittest
from intraday_account_identity import verify_account_identity,AccountIdentityBlocked
class IdentityTests(unittest.TestCase):
    def test_match_does_not_certify_dedication(self):
        x=verify_account_identity(api_fn=lambda b,p:{"id":"paper-account-1"},base="PAPER",expected_account_id="paper-account-1")
        self.assertTrue(x["account_identity_verified"])
        self.assertFalse(x["dedicated_account_proven"])
        self.assertFalse(x["execution_enabled"])
    def test_mismatch_blocks(self):
        with self.assertRaisesRegex(AccountIdentityBlocked,"broker_account_mismatch"):
            verify_account_identity(api_fn=lambda b,p:{"id":"other"},base="PAPER",expected_account_id="paper-account-1")
    def test_exact_account_number_match(self):
        result=verify_account_identity(api_fn=lambda b,p:{"id":"uuid-123","account_number":"PA12345"},base="PAPER",expected_account_id="PA12345")
        self.assertTrue(result["account_identity_verified"])
        self.assertFalse(result["execution_enabled"])
    def test_wrong_account_number_blocks(self):
        with self.assertRaisesRegex(AccountIdentityBlocked,"broker_account_mismatch"):
            verify_account_identity(api_fn=lambda b,p:{"id":"uuid-123","account_number":"PA12345"},base="PAPER",expected_account_id="PA99999")
    def test_missing_secret_blocks_before_api(self):
        def fail(*args):raise AssertionError("API must not be called")
        with self.assertRaisesRegex(AccountIdentityBlocked,"expected_account_missing"):
            verify_account_identity(api_fn=fail,base="PAPER",expected_account_id="")
    def test_missing_id_blocks(self):
        with self.assertRaises(AccountIdentityBlocked):
            verify_account_identity(api_fn=lambda b,p:{"status":"ACTIVE"},base="PAPER",expected_account_id="paper-account-1")
    def test_api_failure_propagates(self):
        def api(*args):raise TimeoutError("private")
        with self.assertRaises(TimeoutError):
            verify_account_identity(api_fn=api,base="PAPER",expected_account_id="paper-account-1")
if __name__=="__main__":unittest.main()
