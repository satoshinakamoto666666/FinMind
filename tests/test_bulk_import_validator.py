import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.bulk_import_validator import validate_and_preview_bulk_import


def test_normalizes_dates_currencies_and_autocategorizes():
    rows = [
        {"date": "11/05/2026", "amount": "$1,250.50", "description": "Whole Foods   Market", "category": ""},
    ]
    res = validate_and_preview_bulk_import(rows)
    assert res["error_count"] == 0
    assert res["auto_corrected_count"] == 1
    norm = res["rows"][0]["normalized"]
    assert norm["date"] == "2026-11-05"
    assert norm["amount"] == 1250.50
    assert norm["description"] == "Whole Foods Market"
    assert norm["category"] == "Groceries"


def test_detects_intra_batch_duplicates_as_warnings():
    rows = [
        {"date": "2026-11-01", "amount": 15.99, "description": "Netflix", "category": "Subscriptions"},
        {"date": "2026-11-01", "amount": "15.99", "description": "NETFLIX", "category": "Subscriptions"},
    ]
    res = validate_and_preview_bulk_import(rows)
    assert res["warning_count"] == 1
    assert res["rows"][1]["status"] == "warning"
    assert "duplicate" in res["rows"][1]["warnings"][0].lower()


def test_flags_invalid_dates_and_negative_amounts_as_errors():
    rows = [
        {"date": "not-a-date", "amount": -20, "description": ""},
    ]
    res = validate_and_preview_bulk_import(rows)
    assert res["error_count"] == 1
    assert res["can_commit_all"] is False
    assert len(res["rows"][0]["errors"]) == 3


def test_warns_when_category_defaults_to_uncategorized():
    rows = [
        {"date": "2026-11-02", "amount": 42.0, "description": "Local Hardware Store"},
    ]
    res = validate_and_preview_bulk_import(rows)
    assert res["rows"][0]["status"] == "warning"
    assert res["rows"][0]["normalized"]["category"] == "Uncategorized"


def test_empty_batch_cannot_commit():
    res = validate_and_preview_bulk_import([])
    assert res["total_rows"] == 0
    assert res["can_commit_all"] is False
