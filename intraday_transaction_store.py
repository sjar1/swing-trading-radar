"""Transactional SQLite reservation prototype, PAPER-only and NO broker writes.

IMPORTANT: A GitHub Actions runner's local SQLite file is ephemeral.
Do not use this backend to authorize unattended trading until it is hosted on
durable shared storage with transactional guarantees and verified recovery.
"""
import json
import sqlite3
from pathlib import Path
from intraday_ledger import propose_reservation, validate_ledger, LedgerBlocked

class StorageBlocked(RuntimeError):
    pass

def connect(path):
    """Create a local test store. Explicitly reject in-memory storage."""
    if not isinstance(path, (str, Path)) or str(path) in (":memory:", ""):
        raise StorageBlocked("nonpersistent_store")
    conn = sqlite3.connect(str(path), timeout=5, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("""CREATE TABLE IF NOT EXISTS intraday_sessions (
        session_date TEXT PRIMARY KEY,
        ledger_json TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision >= 0)
    )""")
    return conn

def seed_session(conn, session_date):
    """Testing/bootstrap only: NEVER auto-seed a trading session from an executor."""
    ledger = {"version": 1, "session_date": session_date, "entries": {}}
    validate_ledger(ledger, session_date)
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("INSERT INTO intraday_sessions VALUES (?, ?, 0)",
                     (session_date, json.dumps(ledger, allow_nan=False)))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise

def reserve(conn, session_date, key, risk):
    """Atomically reserve one signal; rejects duplicates across concurrent writers."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT ledger_json, revision FROM intraday_sessions WHERE session_date=?",
            (session_date,)).fetchone()
        if row is None:
            raise StorageBlocked("session_not_initialized")
        ledger = json.loads(row[0])
        updated = propose_reservation(ledger, session_date, key, risk)
        changed = conn.execute(
            "UPDATE intraday_sessions SET ledger_json=?, revision=revision+1 "
            "WHERE session_date=? AND revision=?",
            (json.dumps(updated, allow_nan=False), session_date, row[1])).rowcount
        if changed != 1:
            raise StorageBlocked("concurrent_revision_conflict")
        conn.commit()
        return updated
    except BaseException:
        conn.rollback()
        raise

def snapshot(conn, session_date):
    row = conn.execute("SELECT ledger_json FROM intraday_sessions WHERE session_date=?",
                       (session_date,)).fetchone()
    if row is None:
        raise StorageBlocked("session_not_initialized")
    ledger = json.loads(row[0])
    validate_ledger(ledger, session_date)
    return ledger

def execution_authorized():
    """This prototype is never sufficient for unattended order execution."""
    return False
