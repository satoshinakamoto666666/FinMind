import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.query_optimizer import (
    RECOMMENDED_INDEXES,
    ensure_financial_indexes,
    explain_financial_query,
    list_existing_indexes,
)


def _create_test_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_id INTEGER,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL
        );
        CREATE TABLE incomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL
        );
        CREATE TABLE budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            period TEXT NOT NULL,
            limit_amount REAL NOT NULL
        );
        CREATE TABLE recurring_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            next_due_date TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        """
    )


def test_ensure_financial_indexes_creates_all_five_indexes():
    conn = sqlite3.connect(":memory:")
    _create_test_schema(conn)
    applied = ensure_financial_indexes(conn)
    assert len(applied) == len(RECOMMENDED_INDEXES) == 5
    existing = {idx["name"] for idx in list_existing_indexes(conn)}
    for item in RECOMMENDED_INDEXES:
        assert item["name"] in existing


def test_explain_query_plan_switches_from_full_scan_to_index():
    conn = sqlite3.connect(":memory:")
    _create_test_schema(conn)
    query = "SELECT category, SUM(amount) FROM expenses WHERE user_id = ? AND date >= ? GROUP BY category"

    before = explain_financial_query(conn, query, (42, "2026-10-01"))
    assert before["uses_index"] is False
    assert before["full_table_scan"] is True

    ensure_financial_indexes(conn)
    after = explain_financial_query(conn, query, (42, "2026-10-01"))
    assert after["uses_index"] is True
    assert after["full_table_scan"] is False


def test_partial_index_used_for_active_recurring_expenses():
    conn = sqlite3.connect(":memory:")
    _create_test_schema(conn)
    ensure_financial_indexes(conn)
    query = "SELECT id, amount FROM recurring_expenses WHERE user_id = ? AND active = 1 AND next_due_date <= ?"
    plan = explain_financial_query(conn, query, (42, "2026-11-30"))
    assert plan["uses_index"] is True
    assert any("idx_recurring_expenses_active_next_due" in step for step in plan["plan_steps"])


def test_idempotent_index_application():
    conn = sqlite3.connect(":memory:")
    _create_test_schema(conn)
    first = ensure_financial_indexes(conn)
    second = ensure_financial_indexes(conn)
    assert first == second
