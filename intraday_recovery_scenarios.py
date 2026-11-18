"""Offline crash/restart scenarios using real fail-closed recovery inspectors."""
from datetime import date
from intraday_recovery_readiness import inspect_recovery

class SimulatedBrokerFailure(RuntimeError):
    pass

def simulate(*,orders=None,positions=None,intents=None,fail_path=None,
             expected_account_id="paper-account"):
    orders=[] if orders is None else orders
    positions=[] if positions is None else positions
    intents=[] if intents is None else intents
    calls=[]
    def api_fn(base,path,method="GET",payload=None):
        if method!="GET" or payload is not None:
            raise AssertionError("unexpected_broker_write")
        calls.append(path)
        if fail_path is not None and path.startswith(fail_path):
            raise SimulatedBrokerFailure("simulated_read_failure")
        if path=="/v2/account":
            return {"id":"paper-account"}
        if path.startswith("/v2/orders?"):
            return orders
        if path=="/v2/positions":
            return positions
        raise AssertionError("unexpected_broker_path")
    def load_fn(db_url,session_date):
        if db_url!="simulated" or session_date!="2026-11-18":
            raise AssertionError("unexpected_database_read")
        return intents
    try:
        result=inspect_recovery(db_url="simulated",session_date=date(2026,11,18),
            api_fn=api_fn,base="PAPER",expected_account_id=expected_account_id,
            load_fn=load_fn)
        return {"outcome":"observed","blockers":result["blockers"],
            "restart_clear":result["restart_clear"],
            "entry_permitted":result["entry_permitted"],
            "execution_enabled":result["execution_enabled"],
            "broker_writes":result["broker_writes"],"read_count":len(calls)}
    except Exception as exc:
        return {"outcome":"blocked","reason":type(exc).__name__,
            "restart_clear":False,"entry_permitted":False,
            "execution_enabled":False,"broker_writes":0,
            "read_count":len(calls)}
