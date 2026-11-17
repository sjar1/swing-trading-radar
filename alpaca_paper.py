"""Submit qualified Trading Radar momentum signals to Alpaca PAPER trading only.

Requires GitHub Actions secrets ALPACA_API_KEY and ALPACA_API_SECRET.
Never uses a live endpoint. No third-party packages.
"""
import json
import math
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote

BASE = "https://paper-api.alpaca.markets"
DATA = Path("docs/data")
MAX_OPEN_POSITIONS = 4
MAX_NEW_ORDERS_PER_RUN = 2
MAX_ACCOUNT_ALLOCATION = 0.25
MAX_TRADE_RISK = 0.01
MAX_TOTAL_OPEN_RISK = 0.04
MIN_EQUITY = 100.0


def request(method, path, payload=None):
    if not path.startswith("/") or "://" in path:
        raise ValueError("Invalid Alpaca API path")
    key = os.environ["ALPACA_API_KEY"].strip()
    secret = os.environ["ALPACA_API_SECRET"].strip()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    body = None if payload is None else json.dumps(payload).encode()
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=25) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as error:
        # Never print request headers, credentials, or response bodies.
        raise RuntimeError(f"Alpaca paper API {method} {path.split('?')[0]} returned HTTP {error.code}") from None


def fresh_signal(signal, today):
    try:
        age = (today - date.fromisoformat(signal["date"])).days
    except (ValueError, TypeError, KeyError):
        return False
    return 0 <= age <= 4


def trade_plan(signal, equity, buying_power):
    price = float(signal["price"])
    stop = float(signal["stop_reference"])
    if not all(map(math.isfinite, (price, stop, equity, buying_power))):
        return None
    if price <= 0 or stop <= 0 or stop >= price:
        return None
    # Entry limit is a 1% price buffer. Size against the worst permitted entry.
    limit = round(price * 1.01, 2)
    if limit <= stop:
        return None
    per_share_risk = limit - stop
    qty = math.floor(min(
        equity * MAX_TRADE_RISK / per_share_risk,
        equity * MAX_ACCOUNT_ALLOCATION / limit,
        buying_power / limit,
    ))
    if qty < 1:
        return None
    target = round(limit + 3 * per_share_risk, 2)
    if target <= limit:
        return None
    return {"qty": qty, "limit": limit, "stop": round(stop, 2), "target": target,
            "risk": round(qty * per_share_risk, 2)}


def main():
    if os.getenv("ALPACA_API_KEY") is None or os.getenv("ALPACA_API_SECRET") is None:
        raise RuntimeError("Alpaca paper credentials are missing; no orders submitted")
    intraday = os.getenv("RADAR_INTRADAY") == "1"
    if intraday:
        from zoneinfo import ZoneInfo
        local = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
        minute = local.hour * 60 + local.minute
        if local.weekday() >= 5 or not 9*60+45 <= minute < 15*60+45:
            print("Outside intraday trading window; no paper orders")
            return
        clock = request("GET", "/v2/clock")
        if not clock.get("is_open"):
            print("Alpaca market clock closed; no paper orders")
            return
    payload = json.loads((DATA / ("intraday_signals.json" if intraday else "signals.json")).read_text())
    generated = datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if generated.tzinfo is None or abs((now - generated).total_seconds()) > (20 * 60 if intraday else 36 * 3600):
        raise RuntimeError("Scanner output is stale; no orders submitted")
    account = request("GET", "/v2/account")
    if account.get("status") != "ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
        raise RuntimeError("Paper account is not active or is blocked")
    equity = float(account["equity"])
    cash = max(0.0, float(account["cash"]))
    buying_power = max(0.0, min(float(account["buying_power"]), cash))
    if equity < MIN_EQUITY:
        raise RuntimeError("Paper account equity below safety minimum")
    positions = request("GET", "/v2/positions")
    open_orders = request("GET", "/v2/orders?status=open&limit=500&nested=true")
    held = {p["symbol"] for p in positions}
    pending = {o["symbol"] for o in open_orders}
    used = held | pending
    existing_risk = 0.0
    # Conservatively reserve full 1% risk budget for each existing holding/order.
    existing_risk = len(used) * MAX_TRADE_RISK * equity
    candidates = [s for s in payload.get("signals", [])
                  if s.get("qualified") is True and s.get("strategy") == "momentum"
                  and fresh_signal(s, now.date())]
    candidates.sort(key=lambda s: float(s.get("score", 0)), reverse=True)
    new_orders = []
    for signal in candidates:
        ticker = signal.get("ticker", "")
        if not ticker.isascii() or not ticker.replace(".", "").isalpha() or len(ticker) > 8:
            continue
        if ticker in used or len(used) >= MAX_OPEN_POSITIONS or len(new_orders) >= MAX_NEW_ORDERS_PER_RUN:
            continue
        if existing_risk + equity * MAX_TRADE_RISK > equity * MAX_TOTAL_OPEN_RISK + 0.0001:
            break
        plan = trade_plan(signal, equity, buying_power)
        if plan is None:
            continue
        client_id = f"radar-{signal['date'].replace('-', '')}-{ticker}"[:48]
        order = {
            "symbol": ticker, "qty": str(plan["qty"]), "side": "buy",
            "type": "limit", "time_in_force": "day",
            "limit_price": str(plan["limit"]),
            "order_class": "bracket",
            "take_profit": {"limit_price": str(plan["target"])},
            "stop_loss": {"stop_price": str(plan["stop"])},
            "client_order_id": client_id,
        }
        # Alpaca rejects reused client IDs, including already filled orders.
        try:
            prior = request("GET", "/v2/orders:by_client_order_id?client_order_id=" + quote(client_id))
            if prior:
                print(f"Skipping {ticker}: client order ID already exists")
                used.add(ticker)
                continue
        except RuntimeError as error:
            if "HTTP 404" not in str(error):
                raise
        submitted = request("POST", "/v2/orders", order)
        new_orders.append({"ticker": ticker, "id": submitted.get("id"), "qty": plan["qty"],
                           "limit": plan["limit"], "stop": plan["stop"], "target": plan["target"]})
        used.add(ticker)
        buying_power -= plan["qty"] * plan["limit"]
        existing_risk += plan["risk"]
        print(f"Submitted PAPER bracket limit order for {ticker}: {plan['qty']} shares")
    # Read-only account snapshot for the public dashboard. Avoid credentials and personal identifiers.
    account_after = request("GET", "/v2/account")
    positions_after = request("GET", "/v2/positions")
    snapshot = {
        "generated_at": now.isoformat(),
        "mode": "ALPACA_PAPER_ONLY",
        "scan_type": "intraday" if intraday else "daily",
        "equity": float(account_after["equity"]),
        "cash": float(account_after["cash"]),
        "buying_power": float(account_after["buying_power"]),
        "positions": [
            {"ticker": p["symbol"], "shares": p["qty"],
             "entry": float(p["avg_entry_price"]),
             "market_value": float(p["market_value"]),
             "unrealized_pl": float(p["unrealized_pl"])}
            for p in positions_after
        ],
        "orders_submitted_this_run": new_orders,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "alpaca_paper.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Paper sync complete; {len(new_orders)} new orders submitted")


if __name__ == "__main__":
    main()
