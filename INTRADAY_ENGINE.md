# Intraday Momentum Engine (PAPER prototype)

Independent of the existing swing strategy. No existing swing files or workflows were changed.

## Safety status
- `intraday_engine.py` hard-codes `https://paper-api.alpaca.markets`; no live endpoint.
- Workflow hard-codes `INTRADAY_PAPER_ORDERS=0`: **dry-run only**.
- `INTRADAY_PAPER_ORDERS=1` is a manual opt-in for PAPER bracket orders, NOT recommended until the limitations below are resolved.
- Tests: `python -m unittest -v test_intraday_engine.py`.
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
1. Implement a persistent end-of-day order cancel/flatten worker and verify it on early-close days; the scan currently **does not flatten positions**.
2. Implement account-wide peak-equity and realized/unrealized intraday drawdown tracking; the current $100 gate uses last equity vs current equity and is not a strict intraday peak drawdown.
3. Coordinate risk across existing swing and intraday strategies and include outstanding stop/target orders correctly.
4. Add quote/spread checks, data feed entitlement validation, corporate action handling, and robust missing-bar treatment.
5. Add durable idempotency and order-state reconciliation (partial fills, cancellations, bracket child orders, retries); a client order ID alone is insufficient.
6. Validate Alpaca cash-account settlement, buying power, broker day-trading restrictions, and account configuration.
7. Use a persistent streaming execution worker for precise exits; GitHub cron is best effort and can be delayed.
8. Add backtesting with fees/slippage and a full paper trade journal before considering any live trading.

Do not merge or enable unattended paper execution until the above blockers are resolved and independently tested.
