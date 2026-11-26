"""Pure preflight for a single manually authorized PAPER lifecycle test.

No broker or database connections. This is not execution authorization.
"""
from decimal import Decimal,InvalidOperation
from intraday_durable_fill_reconciliation import DurableFillBlocked

def preflight(*,account_verified,broker_base,client_order_id,symbol,quantity,
              reference_price,stop_price,target_price,existing_intents,
              existing_open_orders,automated_orders_enabled=False):
    if automated_orders_enabled or account_verified is not True or broker_base!="https://paper-api.alpaca.markets":
        raise DurableFillBlocked("paper_test_preflight_blocked")
    if not isinstance(client_order_id,str) or not client_order_id.startswith("intraday-") or len(client_order_id)>100:
        raise DurableFillBlocked("invalid_client_order_id")
    if symbol not in ("SPY","QQQ","AAPL","MSFT","NVDA","AMD") or type(quantity) is not int or quantity!=1:
        raise DurableFillBlocked("invalid_test_order")
    if type(existing_intents) is not list or type(existing_open_orders) is not list:
        raise DurableFillBlocked("unknown_order_ownership")
    if existing_intents or existing_open_orders:
        raise DurableFillBlocked("nonempty_order_state_requires_reconciliation")
    try:
        price=Decimal(str(reference_price))
        stop=Decimal(str(stop_price))
        target=Decimal(str(target_price))
    except (InvalidOperation,TypeError,ValueError):
        raise DurableFillBlocked("invalid_test_prices") from None
    if not all(x.is_finite() for x in (price,stop,target)) or not (Decimal("10")<=price<=Decimal("150")):
        raise DurableFillBlocked("invalid_test_prices")
    risk=price-stop
    if not (Decimal("0")<risk<=Decimal("25")) or target-price<3*risk:
        raise DurableFillBlocked("invalid_test_risk_reward")
    return {"status":"preflight_constraints_checked","client_order_id":client_order_id,
            "symbol":symbol,"quantity":1,"maximum_risk":str(risk),
            "manual_approval_required":True,"durable_intent_committed":False,
            "broker_acknowledgement_persisted":False,"restart_clear":False,
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
