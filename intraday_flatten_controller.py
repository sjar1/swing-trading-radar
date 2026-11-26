"""Fail-closed, read-only end-of-day PAPER liquidation decision planner.

This module NEVER cancels orders or submits liquidation orders.
The output is a proposed sequence requiring an independently verified executor.
"""
from datetime import datetime
from intraday_calendar import verify_clock, CalendarBlocked

PREFIX = "intraday-"
ACTIVE = frozenset(("new","accepted","pending_new","partially_filled",
                    "pending_cancel","pending_replace","held","accepted_for_bidding"))
TERMINAL = frozenset(("filled","canceled","expired","rejected","replaced","done_for_day"))

def liquidation_plan(calendar_day, broker_clock, now, positions, open_orders,
                     ledger, account_is_dedicated=False):
    base = {"mode":"PAPER_READ_ONLY","execution_enabled":False,
            "cancel_order_ids":[],"close_symbols":[],"blocked":True}
    if not account_is_dedicated:
        return {**base,"reason":"dedicated_account_not_verified"}
    try:
        window=verify_clock(calendar_day,broker_clock,now)
    except (CalendarBlocked,ValueError,TypeError):
        return {**base,"reason":"calendar_unverified"}
    if not window["flatten_due"]:
        return {**base,"reason":"outside_flatten_window","window":window}
    if not isinstance(positions,list) or not isinstance(open_orders,list):
        return {**base,"reason":"invalid_broker_snapshot"}
    if not isinstance(ledger,dict) or ledger.get("version")!=1 or ledger.get("session_date")!=window["date"] or not isinstance(ledger.get("entries"),dict):
        return {**base,"reason":"durable_ledger_unverified"}
    ids=set()
    for order in open_orders:
        if not isinstance(order,dict) or not order.get("id") or not order.get("symbol") or not isinstance(order.get("client_order_id"),str):
            return {**base,"reason":"incomplete_open_order"}
        if order["id"] in ids:
            return {**base,"reason":"duplicate_order_id"}
        ids.add(order["id"])
        if order.get("status") not in ACTIVE:
            return {**base,"reason":"unexpected_open_order_status"}
        if not order["client_order_id"].startswith(PREFIX):
            return {**base,"reason":"unowned_open_order"}
    symbols=set()
    for position in positions:
        if not isinstance(position,dict) or not position.get("symbol"):
            return {**base,"reason":"invalid_position"}
        symbol=position["symbol"]
        if symbol in symbols:
            return {**base,"reason":"duplicate_position"}
        symbols.add(symbol)
        # An order ledger without a fill-to-position attribution cannot prove
        # ownership or quantity, even in a dedicated account.
        return {**base,"reason":"position_fill_attribution_unverified"}
    return {**base,"reason":"no_positions",
            "cancel_order_ids":[o["id"] for o in open_orders],
            "close_symbols":[],"window":window}
