import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.spending_breakdown import classify_category, compute_spending_breakdown


def test_keyword_classification_and_custom_overrides():
    assert classify_category("Monthly Rent") == "essential"
    assert classify_category("Groceries & Market") == "essential"
    assert classify_category("Fine Dining") == "discretionary"
    assert classify_category("401k Retirement") == "savings"
    assert classify_category("Gym", custom_overrides={"gym": "essential"}) == "essential"


def test_spending_breakdown_percentages_and_50_30_20_alignment():
    expenses = [
        {"category": "Rent", "amount": 1500.0},
        {"category": "Groceries", "amount": 500.0},
        {"category": "Dining Out", "amount": 400.0},
        {"category": "Entertainment", "amount": 200.0},
    ]
    res = compute_spending_breakdown(expenses, monthly_net_income=5000.0)
    assert res["totals"]["essential"] == 2000.0
    assert res["totals"]["discretionary"] == 600.0
    assert res["percentages"]["essential"] == 76.92
    assert res["percentages"]["discretionary"] == 23.08
    assert res["rule_50_30_20"]["essential_pct_of_income"] == 40.0
    assert res["rule_50_30_20"]["discretionary_pct_of_income"] == 12.0
    assert res["rule_50_30_20"]["essential_within_50_pct_target"] is True
    assert res["rule_50_30_20"]["discretionary_within_30_pct_target"] is True


def test_empty_expenses_returns_zeroed_breakdown():
    res = compute_spending_breakdown([])
    assert res["total_outflow"] == 0.0
    assert res["percentages"] == {"essential": 0.0, "discretionary": 0.0, "savings": 0.0}


def test_top_categories_sorted_descending():
    expenses = [
        {"category": "Travel", "amount": 800.0},
        {"category": "Shopping", "amount": 250.0},
    ]
    res = compute_spending_breakdown(expenses)
    assert [c["category"] for c in res["top_categories"]["discretionary"]] == ["Travel", "Shopping"]
