"""Bounded, read-only inventory of intraday PAPER durable records by session.

Reports counts only, never order identifiers, credentials, or authorization.
"""
from datetime import date,timedelta
from intraday_durable_fill_reconciliation import DurableFillBlocked

def validate(rows,max_sessions):
    if not isinstance(rows,list) or len(rows)>max_sessions:
        raise DurableFillBlocked("invalid_session_inventory")
    result=[]
    previous=None
    for row in rows:
        if not isinstance(row,(tuple,list)) or len(row)!=3:
            raise DurableFillBlocked("invalid_session_inventory_row")
        day,intents,events=row
        if not isinstance(day,date) or type(intents) is not int or type(events) is not int or intents<0 or events<0:
            raise DurableFillBlocked("invalid_session_inventory_counts")
        if previous is not None and day>=previous:
            raise DurableFillBlocked("unordered_session_inventory")
        previous=day
        result.append({"session_date":day.isoformat(),"durable_intent_count":intents,"persisted_event_count":events})
    return {"status":"bounded_session_inventory","sessions":result,
            "nonempty_session_count":sum(x["durable_intent_count"]>0 for x in result),
            "historical_execution_coverage_proven":False,"account_history_complete":False,
            "restart_clear":False,"entry_permitted":False,"execution_enabled":False,"broker_writes":0}

def inspect(db_url,*,as_of,max_sessions=20):
    if not isinstance(db_url,str) or not db_url or type(as_of) is not date or type(max_sessions) is not int or not 1<=max_sessions<=30:
        raise DurableFillBlocked("invalid_session_inventory_parameters")
    import psycopg
    with psycopg.connect(db_url,connect_timeout=8,sslmode="require") as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("""SELECT i.session_date,COUNT(DISTINCT i.client_order_id),COUNT(e.id)
                           FROM intraday_paper.order_intents i
                           LEFT JOIN intraday_paper.order_events e ON e.client_order_id=i.client_order_id
                           WHERE i.session_date<=%s AND i.session_date>=%s
                           GROUP BY i.session_date ORDER BY i.session_date DESC LIMIT %s""",
                        (as_of,as_of-timedelta(days=90),max_sessions+1))
            rows=cur.fetchall()
            if len(rows)>max_sessions:
                raise DurableFillBlocked("session_inventory_limit_exceeded")
            return validate(rows,max_sessions)
