"""
Database indexing optimization & query plan analyzer for FinMind (#128).
Manages composite & partial indexes and inspects EXPLAIN QUERY PLAN output
to guarantee index-backed scans on high-frequency financial queries.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any


RECOMMENDED_INDEXES: list[dict[str, str]] = [
    {
        "name": "idx_expenses_user_date_category",
        "table": "expenses",
        "ddl": "CREATE INDEX IF NOT EXISTS idx_expenses_user_date_category ON expenses (user_id, date DESC, category)",
        "purpose": "Accelerates date-range and category aggregation queries per user",
    },
    {
        "name": "idx_expenses_user_account_date",
        "table": "expenses",
        "ddl": "CREATE INDEX IF NOT EXISTS idx_expenses_user_account_date ON expenses (user_id, account_id, date DESC)",
        "purpose": "Accelerates multi-account ledger filtering and reconciliation",
    },
    {
        "name": "idx_incomes_user_date",
        "table": "incomes",
        "ddl": "CREATE INDEX IF NOT EXISTS idx_incomes_user_date ON incomes (user_id, date DESC)",
        "purpose": "Accelerates monthly cashflow and income history queries",
    },
    {
        "name": "idx_budgets_user_category_period",
        "table": "budgets",
        "ddl": "CREATE INDEX IF NOT EXISTS idx_budgets_user_category_period ON budgets (user_id, category, period)",
        "purpose": "Accelerates budget lookup and overspend checks",
    },
    {
        "name": "idx_recurring_expenses_active_next_due",
        "table": "recurring_expenses",
        "ddl": "CREATE INDEX IF NOT EXISTS idx_recurring_expenses_active_next_due ON recurring_expenses (user_id, next_due_date) WHERE active = 1",
        "purpose": "Partial index for active recurring bill reminders",
    },
]


def ensure_financial_indexes(conn: sqlite3.Connection) -> list[str]:
    applied: list[str] = []
    cur = conn.cursor()
    existing_tables = {
        row[0]
        for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    for idx in RECOMMENDED_INDEXES:
        if idx["table"] in existing_tables:
            cur.execute(idx["ddl"])
            applied.append(idx["name"])
    conn.commit()
    return applied


def list_existing_indexes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name"
    ).fetchall()
    return [{"name": r[0], "table": r[1], "sql": r[2]} for r in rows]


def explain_financial_query(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] | list[Any] = (),
) -> dict[str, Any]:
    cur = conn.cursor()
    start = time.perf_counter()
    plan_rows = cur.execute(f"EXPLAIN QUERY PLAN {sql}", tuple(params)).fetchall()
    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 3)

    details = [str(r[-1]) for r in plan_rows]
    uses_index = any("USING INDEX" in d.upper() or "USING COVERING INDEX" in d.upper() for d in details)
    full_table_scan = any("SCAN " in d.upper() and "USING INDEX" not in d.upper() for d in details)

    return {
        "sql": sql,
        "plan_steps": details,
        "uses_index": uses_index,
        "full_table_scan": full_table_scan,
        "analysis_time_ms": elapsed_ms,
    }
