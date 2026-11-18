# Intraday PAPER safety status

The intraday engine is **PAPER dry-run only**. No order submission, cancellation,
position liquidation, or autonomous recovery is authorized.

## Implemented (read-only / simulated)
- Dedicated PAPER account data and signal scanning.
- Durable order-intent and acknowledgement state-machine simulations.
- Broker order ownership checks.
- Alpaca fill activity collection and session-level Supabase reconciliation.
- Strict monitoring heartbeat freshness validator.
- CI tests, logs, scheduled safety checks, and failure issues.

## Not yet certified
- Alpaca live PAPER response schema and full pagination across order history.
- Complete account-history proof, bracket-child ownership, partial fills and
  adjustments, and exact broker-to-position attribution.
- Durable heartbeat producer and continuous runtime with outage detection.
- Idempotent cancel/close executor, acknowledgement checks, and emergency
  liquidation under market and network failure conditions.
- End-to-end isolated PAPER trading pilot.

A healthy heartbeat check is **not** permission to trade. The monitor validator
has no heartbeat producer or deployment yet, and GitHub Actions is not a
continuous low-latency trading monitor.

To manually run the broker diagnostic, use GitHub Actions >
**Intraday PAPER Fill History Diagnostic** > Run workflow. It performs GET
requests only and returns aggregate counts, never credentials or order IDs.
If a read-only diagnostic fails, do not enable execution.
