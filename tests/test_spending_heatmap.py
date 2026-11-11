import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.spending_heatmap import build_spending_heatmap


def test_generates_intensity_buckets_and_hotspots():
    txs = [
        {"date": "2026-11-02", "amount": 15.0, "category": "Coffee"},
        {"date": "2026-11-03", "amount": 45.0, "category": "Groceries"},
        {"date": "2026-11-04", "amount": 120.0, "category": "Dining"},
        {"date": "2026-11-06", "amount": 480.0, "category": "Electronics"},
    ]
    res = build_spending_heatmap(txs)
    assert res["active_days_count"] == 4
    assert res["total_spend"] == 660.0
    intensities = {c["date"]: c["intensity"] for c in res["calendar_heatmap"]}
    assert intensities["2026-11-02"] == 1
    assert intensities["2026-11-06"] == 4
    assert res["hotspots"]["peak_date"]["date"] == "2026-11-06"


def test_aggregates_multiple_transactions_on_same_day():
    txs = [
        {"date": "2026-11-02", "amount": 20.0, "category": "Food"},
        {"date": "2026-11-02", "amount": 30.0, "category": "Transport"},
    ]
    res = build_spending_heatmap(txs)
    assert res["active_days_count"] == 1
    assert res["calendar_heatmap"][0]["amount"] == 50.0
    assert res["calendar_heatmap"][0]["transaction_count"] == 2


def test_category_weekday_matrix():
    txs = [
        {"date": "2026-11-02", "amount": 25.0, "category": "Dining"},  # Monday
        {"date": "2026-11-09", "amount": 35.0, "category": "Dining"},  # Monday
    ]
    res = build_spending_heatmap(txs)
    assert res["category_weekday_matrix"]["Dining"]["Monday"] == 60.0


def test_empty_transactions_returns_zeroed_heatmap():
    res = build_spending_heatmap([])
    assert res["active_days_count"] == 0
    assert res["total_spend"] == 0.0
    assert res["hotspots"]["peak_date"] is None
