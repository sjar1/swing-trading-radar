-- Intraday PAPER trading persistence schema. Run in Supabase SQL Editor.
-- No order execution is enabled by this migration.
create schema if not exists intraday_paper;
create table if not exists intraday_paper.sessions (
  session_date date primary key,
  prior_close_equity numeric(18,4) not null check (prior_close_equity > 0),
  peak_equity numeric(18,4) not null check (peak_equity > 0),
  last_equity numeric(18,4) not null check (last_equity > 0),
  drawdown numeric(18,4) not null default 0 check (drawdown >= 0),
  trading_blocked boolean not null default true,
  revision bigint not null default 0 check (revision >= 0),
  updated_at timestamptz not null default now()
);
create table if not exists intraday_paper.order_intents (
  client_order_id text primary key check (client_order_id ~ '^intraday-[A-Za-z0-9-]+$'),
  session_date date not null references intraday_paper.sessions(session_date),
  symbol text not null check (symbol ~ '^[A-Z]{1,8}$'),
  strategy text not null check (strategy in ('opening_range_breakout','vwap_reclaim')),
  reserved_risk numeric(18,4) not null check (reserved_risk > 0 and reserved_risk <= 25),
  state text not null default 'reserved' check (state in
    ('reserved','submitted','accepted','partially_filled','filled','canceled','rejected','expired','closed','unknown')),
  broker_order_id text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists order_intents_session_idx on intraday_paper.order_intents(session_date);
create table if not exists intraday_paper.equity_samples (
  id bigint generated always as identity primary key,
  session_date date not null references intraday_paper.sessions(session_date),
  sampled_at timestamptz not null,
  equity numeric(18,4) not null check (equity > 0),
  unique (session_date, sampled_at)
);
create table if not exists intraday_paper.order_events (
  id bigint generated always as identity primary key,
  client_order_id text not null references intraday_paper.order_intents(client_order_id),
  broker_order_id text,
  broker_status text not null,
  event_at timestamptz not null,
  observed_at timestamptz not null default now(),
  payload jsonb not null default '{}'::jsonb,
  unique (client_order_id, broker_order_id, broker_status, event_at)
);
-- Prevent anonymous and authenticated API users from accessing trading records.
revoke all on schema intraday_paper from public, anon, authenticated;
revoke all on all tables in schema intraday_paper from public, anon, authenticated;
revoke all on all sequences in schema intraday_paper from public, anon, authenticated;
alter default privileges in schema intraday_paper revoke all on tables from public, anon, authenticated;
alter default privileges in schema intraday_paper revoke all on sequences from public, anon, authenticated;
-- No public RPC functions or trading-execution permissions are created.
