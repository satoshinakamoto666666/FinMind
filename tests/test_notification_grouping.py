import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.notification_grouping import (
    classify_priority,
    group_and_prioritize_notifications,
)


def test_priority_ordering_and_grouping():
    raw = [
        {"id": 1, "event_type": "weekly_digest", "category": "digest", "title": "Weekly Summary", "timestamp": 1000},
        {"id": 2, "event_type": "budget_warning", "category": "budgets", "title": "Dining at 85%", "timestamp": 1050},
        {"id": 3, "event_type": "budget_exceeded", "category": "budgets", "title": "Shopping at 105%", "timestamp": 1100},
        {"id": 4, "event_type": "security_alert", "category": "security", "title": "New device login", "timestamp": 1020},
    ]
    res = group_and_prioritize_notifications(raw)
    assert res["group_count"] == 3
    assert res["groups"][0]["group_key"] == "security"
    assert res["groups"][0]["highest_priority"] == "critical"
    assert res["groups"][1]["group_key"] == "budgets"
    assert res["groups"][1]["count"] == 2
    assert res["groups"][1]["highest_priority"] == "high"
    assert res["groups"][2]["group_key"] == "digest"


def test_deduplication_within_cooldown_window():
    raw = [
        {"id": 1, "event_type": "bill_due_soon", "entity_id": "rent", "title": "Rent due", "timestamp": 1000},
        {"id": 2, "event_type": "bill_due_soon", "entity_id": "rent", "title": "Rent due", "timestamp": 1120},
        {"id": 3, "event_type": "bill_due_soon", "entity_id": "rent", "title": "Rent due", "timestamp": 1600},
    ]
    res = group_and_prioritize_notifications(raw, dedup_window_seconds=300)
    assert res["suppressed_duplicates"] == 1
    assert res["total_active"] == 2


def test_large_dollar_amount_escalates_priority():
    assert classify_priority({"event_type": "subscription_renewal", "amount": 1200.0}) == "high"
    assert classify_priority({"event_type": "subscription_renewal", "amount": 6000.0}) == "critical"


def test_critical_groups_remain_uncollapsed():
    raw = [
        {"id": 1, "event_type": "security_alert", "category": "security", "title": "Alert A", "timestamp": 100},
        {"id": 2, "event_type": "overdraft_risk", "category": "security", "title": "Alert B", "timestamp": 200},
    ]
    res = group_and_prioritize_notifications(raw)
    assert res["groups"][0]["collapsed"] is False


def test_empty_notifications_list():
    res = group_and_prioritize_notifications([])
    assert res["total_active"] == 0
    assert res["groups"] == []
