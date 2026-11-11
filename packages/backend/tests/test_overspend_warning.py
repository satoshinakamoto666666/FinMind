import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.overspend_warning import evaluate_category_early_warnings


def test_detects_over_budget_critical_and_pace_warnings():
    expenses = [
        {"category": "Dining", "amount": 320.0},      # over $300 budget
        {"category": "Shopping", "amount": 250.0},    # 83.3% used at day 10 -> critical
        {"category": "Entertainment", "amount": 80.0}, # 40% used at day 10 -> projects to $240 > $200 -> warning
        {"category": "Groceries", "amount": 150.0},   # 25% used at day 10 -> projects to $450 <= $600 -> ok
    ]
    budgets = {
        "Dining": 300.0,
        "Shopping": 300.0,
        "Entertainment": 200.0,
        "Groceries": 600.0,
    }
    res = evaluate_category_early_warnings(expenses, budgets, day_of_month=10, days_in_month=30)
    assert res["active_alerts_count"] == 3
    severities = {w["category"]: w["severity"] for w in res["all_categories"]}
    assert severities["Dining"] == "over_budget"
    assert severities["Shopping"] == "critical"
    assert severities["Entertainment"] == "warning"
    assert severities["Groceries"] == "ok"


def test_computes_safe_daily_allowance_accurately():
    expenses = [{"category": "Groceries", "amount": 200.0}]
    budgets = {"Groceries": 500.0}
    res = evaluate_category_early_warnings(expenses, budgets, day_of_month=15, days_in_month=30)
    cat = res["all_categories"][0]
    assert cat["remaining_budget"] == 300.0
    assert cat["safe_daily_allowance"] == 20.0


def test_alerts_ordered_by_severity_descending():
    expenses = [
        {"category": "A", "amount": 110.0},
        {"category": "B", "amount": 90.0},
    ]
    budgets = {"A": 100.0, "B": 100.0}
    res = evaluate_category_early_warnings(expenses, budgets, day_of_month=15, days_in_month=30)
    assert [a["category"] for a in res["alerts"]] == ["A", "B"]


def test_handles_last_day_of_month_without_division_by_zero():
    res = evaluate_category_early_warnings(
        [{"category": "Dining", "amount": 90.0}],
        {"Dining": 100.0},
        day_of_month=30,
        days_in_month=30,
    )
    assert res["all_categories"][0]["safe_daily_allowance"] == 0.0
