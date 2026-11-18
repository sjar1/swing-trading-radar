"""Read-only PAPER account risk assessment; never grants execution permission."""
from decimal import Decimal,InvalidOperation

class RiskBlocked(RuntimeError):
    pass

def number(value):
    try:
        n=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):
        raise RiskBlocked("invalid_numeric_field")
    if not n.is_finite():raise RiskBlocked("nonfinite_numeric_field")
    return n

def assess(account,positions,open_orders,*,daily_loss_limit="100",max_exposure="2000",max_positions=2):
    if not isinstance(account,dict) or not isinstance(positions,list) or not isinstance(open_orders,list):
        raise RiskBlocked("invalid_snapshot")
    if account.get("status")!="ACTIVE" or account.get("trading_blocked") is not False or account.get("account_blocked") is not False:
        raise RiskBlocked("account_not_ready")
    equity=number(account.get("equity"))
    last=number(account.get("last_equity"))
    cash=number(account.get("cash"))
    if equity<=0 or last<=0 or cash<0:raise RiskBlocked("invalid_account_balance")
    exposure=Decimal(0)
    held=set()
    for p in positions:
        if not isinstance(p,dict) or not isinstance(p.get("symbol"),str) or p.get("side")!="long":
            raise RiskBlocked("invalid_position")
        symbol=p["symbol"]
        if symbol in held:raise RiskBlocked("duplicate_position")
        held.add(symbol)
        exposure+=abs(number(p.get("market_value")))
    pending=set()
    for o in open_orders:
        if not isinstance(o,dict) or not isinstance(o.get("symbol"),str) or o.get("side") not in ("buy","sell"):
            raise RiskBlocked("invalid_open_order")
        if o["side"]=="buy":
            price=o.get("limit_price")
            qty=o.get("qty")
            if price is None or qty is None:
                raise RiskBlocked("unpriced_buy_order")
            p=number(price);q=number(qty)
            if p<=0 or q<=0:raise RiskBlocked("invalid_buy_order")
            exposure+=p*q
            pending.add(o["symbol"])
    daily_loss=last-equity
    reasons=[]
    if daily_loss>=number(daily_loss_limit):reasons.append("daily_loss_limit")
    if exposure>=number(max_exposure):reasons.append("exposure_limit")
    if len(held|pending)>=max_positions:reasons.append("position_limit")
    return {"risk_observed":True,"within_limits":not reasons,"problems":reasons,
            "exposure":str(exposure),"daily_loss":str(daily_loss),
            "entry_permitted":False,"execution_enabled":False,"broker_writes":0}
