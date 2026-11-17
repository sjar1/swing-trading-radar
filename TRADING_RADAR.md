# Trading Radar v1 (research prototype)
This repository contains a **signals-only** daily scanner, dashboard, position sizing, and a momentum-only backtest prototype. No broker orders are placed.

## Run
```bash
pip install -r requirements.txt
python trading_radar.py --run
python backtest.py --ticker SOFI
```
Open `docs/index.html` through GitHub Pages or a local web server. Configure Pages to deploy from `/docs` on the branch you merge into the default branch. The scheduled workflow runs at 22:30 UTC on weekdays; GitHub scheduling is best-effort and may be delayed. It commits daily score snapshots to the current branch.

## Risk limits
Initial equity $5,000, risk budget 1% of equity, maximum 25% allocation per position. The prototype calculator does not enforce portfolio-wide risk, sector exposure, or settlement restrictions; these must be checked manually. Stops may gap.

## Important limitations / next steps
- Price data from yfinance is research-grade and can be incomplete or delayed. Do not use this as a live execution feed.
- No validated historical short interest, days-to-cover, borrow rates, market-cap feed, or verified catalysts are included. Squeeze and reversal entries therefore remain **disabled**, rather than fabricating metrics.
- Ranking scores are heuristics, not calibrated win probabilities.
- Backtest covers momentum entries only, one position at a time, with simplified fills and exits; it does not yet implement partial profit-taking, survivorship-free universes, sector controls, or walk-forward evaluation.
- Workflow and dashboard must be verified after merge and Pages configuration.
- Paper trade and validate out of sample before any real-money use.
