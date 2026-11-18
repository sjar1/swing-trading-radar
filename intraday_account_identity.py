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
    expected=expected_account_id.strip()
    number=account.get("account_number")
    # Alpaca exposes both a UUID `id` and a shorter `account_number`.
    # Require an exact match to either verified broker-provided identifier.
    id_matches=hmac.compare_digest(actual,expected)
    number_matches=isinstance(number,str) and bool(number.strip()) and hmac.compare_digest(number,expected)
    if not (id_matches or number_matches):
        raise AccountIdentityBlocked("broker_account_mismatch")
    return {"account_identity_verified":True,"dedicated_account_proven":False,
            "account_history_complete":False,"position_attribution_certified":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
