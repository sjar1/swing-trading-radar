-- Optional isolated intraday PAPER recovery checkpoint storage.
-- Migration must be applied manually after review. No broker execution.
create table if not exists intraday_paper.recovery_checkpoints (
  session_date date primary key references intraday_paper.sessions(session_date),
  checkpoint jsonb not null,
  observed_at timestamptz not null default now(),
  revision bigint not null default 0 check (revision >= 0),
  check (jsonb_typeof(checkpoint) = 'object')
);
revoke all on intraday_paper.recovery_checkpoints from public, anon, authenticated;
-- Checkpoints alone never certify broker ownership or enable trading.
