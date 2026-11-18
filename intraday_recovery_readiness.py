"""Fail-closed restart inspection joining durable records and PAPER broker state."""
from datetime import date
from intraday_durable_ownership_probe import inspect_durable_ownership
from intraday_restart_safety import inspect_restart
from intraday_position_snapshot import inspect_positions
from intraday_account_identity import verify_account_identity

def inspect_recovery(*,db_url,session_date,api_fn,base,expected_account_id,load_fn):
    if type(session_date) is not date or not callable(api_fn) or not callable(load_fn):
        raise ValueError("invalid_recovery_dependencies")
    identity=verify_account_identity(api_fn=api_fn,base=base,expected_account_id=expected_account_id)
    ownership=inspect_durable_ownership(db_url=db_url,session_date=session_date,
        api_fn=api_fn,base=base,load_fn=load_fn)
    positions=inspect_positions(api_fn=api_fn,base=base)
    restart=inspect_restart(account_verified=identity["account_identity_verified"],
        position_count=positions["position_count"],
        open_order_count=ownership["open_orders_observed"],
        history_complete=False,attribution_certified=False)
    return {"status":"recovery_observed","account_identity_verified":True,
        "durable_intent_count":ownership["durable_intent_count"],
        "open_order_count":ownership["open_orders_observed"],
        "position_count":positions["position_count"],
        "open_order_identity_consistent":ownership["open_order_identity_consistent"],
        **restart,"account_history_complete":False,"position_attribution_certified":False,
        "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
