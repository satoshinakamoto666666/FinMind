import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.lifestyle_inflation import detect_lifestyle_inflation


def test_detects_high_lifestyle_creep_when_discretionary_outpaces_income():
    snapshots = [
        {"month": "2026-01", "income": 5000, "categories": {"Rent": 1500, "Dining": 300, "Shopping": 200}},
        {"month": "2026-02", "income": 5000, "categories": {"Rent": 1500, "Dining": 320, "Shopping": 220}},
        {"month": "2026-03", "income": 5500, "categories": {"Rent": 1500, "Dining": 600, "Shopping": 550}},
        {"month": "2026-04", "income": 5500, "categories": {"Rent": 1500, "Dining": 650, "Shopping": 600}},
    ]
    res = detect_lifestyle_inflation(snapshots)
    assert res["lifestyle_inflation_detected"] is True
    assert res["severity"] == "high"
    assert res["discretionary_growth_pct"] > res["income_growth_pct"]
    assert res["annualized_creep_cost"] > 5000.0
    assert res["category_drivers"][0]["category"] in {"Shopping", "Dining"}


def test_no_inflation_when_savings_grow_with_income():
    snapshots = [
        {"month": "2026-01", "income": 5000, "categories": {"Rent": 1500, "Dining": 400}},
        {"month": "2026-02", "income": 6000, "categories": {"Rent": 1500, "Dining": 410}},
    ]
    res = detect_lifestyle_inflation(snapshots)
    assert res["lifestyle_inflation_detected"] is False
    assert res["severity"] == "none"
    assert res["savings_rate_delta_pct"] > 0


def test_ignores_essential_categories_in_creep_drivers():
    snapshots = [
        {"month": "2026-01", "income": 5000, "categories": {"Rent": 1500, "Utilities": 150, "Dining": 200}},
        {"month": "2026-02", "income": 5000, "categories": {"Rent": 1800, "Utilities": 250, "Dining": 205}},
    ]
    res = detect_lifestyle_inflation(snapshots)
    assert res["lifestyle_inflation_detected"] is False
    assert all(d["category"] not in {"Rent", "Utilities"} for d in res["category_drivers"])


def test_single_snapshot_returns_graceful_default():
    res = detect_lifestyle_inflation([{"month": "2026-01", "income": 4000, "categories": {"Rent": 1200}}])
    assert res["lifestyle_inflation_detected"] is False
