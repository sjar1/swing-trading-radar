"""Read-only Supabase PostgreSQL connectivity probe. Never submits orders."""
import os
import sys

def main():
    url = os.getenv("INTRADAY_DATABASE_URL", "")
    if not url:
        print("BLOCKED: INTRADAY_DATABASE_URL GitHub secret is not configured.")
        return 2
    if not url.startswith(("postgresql://", "postgres://")):
        print("BLOCKED: expected a PostgreSQL connection URL.")
        return 2
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=8, sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("""
                    SELECT count(*) FROM information_schema.tables
                    WHERE table_schema = 'intraday_paper'
                    AND table_name IN ('sessions','order_intents','equity_samples','order_events')
                """)
                count = cur.fetchone()[0]
                if count != 4:
                    print(f"BLOCKED: only {count}/4 intraday tables are visible.")
                    return 3
                cur.execute("SELECT count(*) FROM intraday_paper.sessions")
                sessions = cur.fetchone()[0]
                print(f"PASS: read-only database connection; 4/4 tables; {sessions} sessions.")
                return 0
    except Exception as exc:
        print(f"BLOCKED: database connectivity or permission check failed ({type(exc).__name__}).")
        return 3

if __name__ == "__main__":
    sys.exit(main())
