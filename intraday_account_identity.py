"""Read-only dedicated Alpaca PAPER account identity gate.

Caller must provide the expected account ID via a GitHub secret. Never return
or log either ID. Identity equality is not proof of exclusive account use.
"""
import hmac
class AccountIdentityBlocked(ValueError):pass

def verify_account_identity(*,api_fn,base,expected_account_id):
    if not isinstance(expected_account_id,str) or not expected_account_id.strip():
        raise AccountIdentityBlocked("expected_account_missing")
    account=api_fn(base,"/v2/account")
    if not isinstance(account,dict):
        raise AccountIdentityBlocked("invalid_account_snapshot")
    actual=account.get("id")
    if not isinstance(actual,str) or not actual.strip():
        raise AccountIdentityBlocked("missing_broker_account_id")
    if not hmac.compare_digest(actual,expected_account_id.strip()):
        raise AccountIdentityBlocked("broker_account_mismatch")
    return {"account_identity_verified":True,"dedicated_account_proven":False,
            "account_history_complete":False,"position_attribution_certified":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
