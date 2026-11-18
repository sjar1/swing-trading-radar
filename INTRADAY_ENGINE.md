# Intraday Momentum Engine (PAPER prototype)

Independent of the existing swing strategy. No existing swing files or workflows were changed.

## Safety status
- `intraday_engine.py` hard-codes `https://paper-api.alpaca.markets`; no live endpoint.
- Workflow hard-codes `INTRADAY_PAPER_ORDERS=0`: **dry-run only**.
- Order submission is **not implemented/enabled** in this branch; setting `INTRADAY_PAPER_ORDERS=1` fails closed with `execution_not_certified`. No paper or live orders can be placed by this engine.
- Tests: `python -m unittest -v test_intraday_engine.py test_intraday_lifecycle.py` (15 tests; GitHub Actions results not yet verified).\n- `intraday_lifecycle.py` is a read-only risk and end-of-day planning audit; it never cancels or liquidates orders.\n- The lifecycle audit refuses to certify risk without durable peak equity and never assumes a shared-account position belongs to the intraday bot.
- Workflow uploads JSON diagnostics as a GitHub Actions artifact, not as an automatically published dashboard snapshot.
- Dashboard at `docs/intraday.html` displays a JSON snapshot only if separately published.

## Rules
Watchlist: SPY, QQQ, AAPL, MSFT, NVDA, AMD; IEX 1-minute bars.
Opening range = first 15 complete bars; entry only on confirmed breakout.
VWAP reclaim = prior close below VWAP and latest completed close above VWAP.
Volume > 1.5x preceding 20-minute average. $10–$150 stock price.
Risk budget $25/trade, 3:1 target, $100 prior-close daily loss gate,
max 2 existing positions/orders, max $2,000 estimated exposure, max 5 daily entries.
Entry window 09:45–15:15 ET, weekdays and broker market-open.

## Critical blockers before unattended paper execution
1. Implement a persistent end-of-day order cancel/flatten worker with **provable position ownership** and verify it on early-close days; read-only planning is now present, but **no positions are flattened**.
2. Implement account-wide peak-equity and realized/unrealized intraday drawdown tracking; the current $100 gate uses last equity vs current equity and is not a strict intraday peak drawdown.
3. Coordinate risk across existing swing and intraday strategies and include outstanding stop/target orders correctly.
4. Add quote/spread checks, data feed entitlement validation, corporate action handling, and robust missing-bar treatment.
5. Add durable idempotency and order-state reconciliation (partial fills, cancellations, bracket child orders, retries); a client order ID alone is insufficient.
6. Validate Alpaca cash-account settlement, buying power, broker day-trading restrictions, and account configuration.
7. Use a persistent streaming execution worker for precise exits; GitHub cron is best effort and can be delayed.
8. Add backtesting with fees/slippage and a full paper trade journal before considering any live trading.

Do not merge or enable unattended paper execution until the above blockers are resolved and independently tested.
