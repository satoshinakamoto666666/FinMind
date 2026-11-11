import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.savings_opportunities import detect_savings_opportunities


def test_detects_duplicate_subscriptions_and_ranks_by_impact():
    subs = [
        {"name": "StreamPlus", "group": "video_streaming", "monthly_cost": 15.99, "active": True},
        {"name": "CinemaMax", "group": "video_streaming", "monthly_cost": 19.99, "active": True},
        {"name": "CloudBackup", "group": "storage", "monthly_cost": 9.99, "active": True},
    ]
    report = detect_savings_opportunities(expenses=[], subscriptions=subs)
    assert report["opportunities_count"] == 1
    opp = report["opportunities"][0]
    assert opp["rule_id"] == "duplicate_subscriptions"
    assert opp["estimated_monthly_savings"] == 15.99
    assert opp["estimated_annual_savings"] == round(15.99 * 12, 2)


def test_detects_category_overspend_micro_spend_and_weekend_surge():
    expenses = [
        {"amount": 8.50, "category": "coffee", "date": "2026-11-02"},
        {"amount": 7.25, "category": "coffee", "date": "2026-11-03"},
        {"amount": 9.00, "category": "coffee", "date": "2026-11-04"},
        {"amount": 6.75, "category": "coffee", "date": "2026-11-05"},
        {"amount": 8.00, "category": "coffee", "date": "2026-11-06"},
        {"amount": 220.00, "category": "dining", "date": "2026-11-07"},  # Saturday
        {"amount": 180.00, "category": "dining", "date": "2026-11-08"},  # Sunday
    ]
    baselines = {"dining": 200.0}
    report = detect_savings_opportunities(
        expenses=expenses,
        category_baselines=baselines,
        idle_cash_balance=5000.0,
    )
    rule_ids = {o["rule_id"] for o in report["opportunities"]}
    assert "category_overspend" in rule_ids
    assert "high_frequency_micro_spend" in rule_ids
    assert "weekend_spending_surge" in rule_ids
    assert "idle_cash_yield" in rule_ids
    assert report["total_estimated_monthly_savings"] > 200.0
