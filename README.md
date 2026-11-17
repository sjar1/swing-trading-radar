# Swing Trading Radar

Independent swing-trading research bot for momentum breakouts, candidate scoring, risk-based position sizing, and historical snapshots. **Signals only; no brokerage execution.**

## Links
- [Trading dashboard (after Pages setup)](https://sjar1.github.io/swing-trading-radar/)
- [Scanner workflow](https://github.com/sjar1/swing-trading-radar/actions/workflows/trading-radar.yml)
- [Original short-squeeze project](https://github.com/sjar1/short-squeeze-radar)

## Setup
Run the **Trading Radar Scan** workflow once on `main`. In Settings > Pages, select Deploy from branch > `main` > `/docs`. Scheduled scans run on weekdays. See [TRADING_RADAR.md](TRADING_RADAR.md) for limitations and backtesting details.

The scanner currently implements momentum signals; catalyst and verified short-interest inputs are not configured. The ranking score is not a probability. Validate through paper trading before real-money use.
