"""Controlled Alpaca PAPER bracket-order test. Never accesses live trading.
Manual-only: --execute is required to submit a real paper order.
The default is a read-only validation and preview.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from alpaca_paper import request, trade_plan, MAX_TRADE_RISK, MAX_OPEN_POSITIONS

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--symbol",default="SPY")
    args=parser.parse_args()
    symbol=args.symbol.upper().strip()
    if symbol not in ("SPY","QQQ"):
        raise SystemExit("Only SPY or QQQ permitted for controlled execution test")
    clock=request("GET","/v2/clock")
    account=request("GET","/v2/account")
    positions=request("GET","/v2/positions")
    orders=request("GET","/v2/orders?status=open&limit=500&nested=true")
    quote=request("GET","/v2/stocks/"+symbol+"/quotes/latest") if False else None
    print("PAPER endpoint verified; market open:",bool(clock.get("is_open")))
    print("Account status:",account.get("status"),"existing positions:",len(positions),"open orders:",len(orders))
    if not args.execute:
        print("DRY RUN ONLY: credentials, account, clock and positions checked; no order submitted")
        return
    if not clock.get("is_open") or account.get("status")!="ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
        raise SystemExit("Market closed or paper account blocked; no order")
    if positions or orders:
        raise SystemExit("Execution test requires no existing positions or open orders; no order")
    # Use Alpaca's paper market data snapshot for a fresh test reference price.
    import os
    from urllib.parse import urlencode
    from urllib.request import Request,urlopen
    url="https://data.alpaca.markets/v2/stocks/"+symbol+"/snapshot?"+urlencode({"feed":"iex"})
    headers={"APCA-API-KEY-ID":os.environ["ALPACA_API_KEY"],"APCA-API-SECRET-KEY":os.environ["ALPACA_API_SECRET"]}
    with urlopen(Request(url,headers=headers),timeout=25) as resp: snap=json.load(resp)
    trade=snap.get("latestTrade") or {}
    ts=trade.get("t")
    if not ts or abs((datetime.now(timezone.utc)-datetime.fromisoformat(ts.replace("Z","+00:00"))).total_seconds())>120:
        raise SystemExit("No fresh IEX trade; no order")
    price=float(trade["p"])
    if not math.isfinite(price) or price<=0:raise SystemExit("Invalid price")
    # Bracket buy limit 1% above reference, stop 2% below reference, target 3R.
    limit=round(price*1.01,2)
    stop=round(price*0.98,2)
    if stop<=0 or limit<=stop:raise SystemExit("Invalid stop/limit")
    equity=float(account["equity"])
    cash=min(float(account["cash"]),float(account["buying_power"]))
    # Test-only allocation: at most $750 notional and $5 planned stop loss.
    qty=math.floor(min(750/limit,5/(limit-stop),equity*MAX_TRADE_RISK/(limit-stop),cash/limit))
    if qty<1:raise SystemExit("Test risk/notional caps cannot safely buy one share; no order")
    target=round(limit+3*(limit-stop),2)
    order={"symbol":symbol,"qty":str(qty),"side":"buy","type":"limit",
           "time_in_force":"day","limit_price":str(limit),"order_class":"bracket",
           "take_profit":{"limit_price":str(target)},
           "stop_loss":{"stop_price":str(stop)},
           "client_order_id":"radar-test-"+datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}
    result=request("POST","/v2/orders",order)
    print("PAPER TEST ORDER SUBMITTED:",json.dumps({"symbol":symbol,"qty":qty,"limit":limit,"stop":stop,"target":target,"order_id":result.get("id"),"status":result.get("status")}))
    print("A submitted limit order may remain open or unfilled. Check Alpaca PAPER orders and positions.")

if __name__=="__main__":main()
