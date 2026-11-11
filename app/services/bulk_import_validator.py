"""
Bulk Import Validation & Preview Improvements (#115).

Validates and normalizes raw CSV/JSON transaction rows prior to database commit:
- Date format normalization (YYYY-MM-DD, MM/DD/YYYY, DD-MM-YYYY, YYYY/MM/DD)
- Currency symbol & thousand-separator stripping ($1,250.50 -> 1250.5)
- Merchant whitespace normalization & auto-categorization suggestions
- Duplicate detection across both existing ledger rows and intra-batch rows
- Structured row-level errors, warnings, and auto-correction diffs
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y")

MERCHANT_CATEGORY_RULES = {
    "uber": "Transportation",
    "lyft": "Transportation",
    "shell": "Transportation",
    "whole foods": "Groceries",
    "trader joe": "Groceries",
    "kroger": "Groceries",
    "netflix": "Subscriptions",
    "spotify": "Subscriptions",
    "starbucks": "Dining",
    "chipotle": "Dining",
}


def _parse_date(raw: Any) -> tuple[str | None, bool]:
    s = str(raw or "").strip()
    if not s:
        return None, False
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            norm = dt.strftime("%Y-%m-%d")
            return norm, (norm != s)
        except ValueError:
            continue
    return None, False


def _parse_amount(raw: Any) -> tuple[float | None, bool]:
    if isinstance(raw, (int, float)):
        val = round(float(raw), 2)
        return (val if val > 0 else None), False
    s = str(raw or "").strip()
    if not s:
        return None, False
    cleaned = re.sub(r"[$€£₹,\s]", "", s)
    try:
        val = round(float(cleaned), 2)
        if val <= 0:
            return None, False
        return val, (cleaned != s)
    except ValueError:
        return None, False


def validate_and_preview_bulk_import(
    rows: list[dict[str, Any]],
    existing_signatures: set[str] | None = None,
) -> dict[str, Any]:
    seen_sigs = set(existing_signatures or set())
    preview_rows: list[dict[str, Any]] = []
    ready_count = 0
    warning_count = 0
    error_count = 0
    corrected_count = 0

    for idx, r in enumerate(rows, start=1):
        errors: list[str] = []
        warnings: list[str] = []
        corrections: list[str] = []

        norm_date, date_corrected = _parse_date(r.get("date"))
        if not norm_date:
            errors.append("Invalid or missing date")
        elif date_corrected:
            corrections.append(f"Normalized date '{r.get('date')}' -> '{norm_date}'")

        norm_amt, amt_corrected = _parse_amount(r.get("amount"))
        if norm_amt is None:
            errors.append("Amount must be a positive number")
        elif amt_corrected:
            corrections.append(f"Normalized amount '{r.get('amount')}' -> {norm_amt:.2f}")

        raw_desc = str(r.get("description") or r.get("merchant") or "").strip()
        norm_desc = re.sub(r"\s+", " ", raw_desc)
        if not norm_desc:
            errors.append("Missing description or merchant name")
        elif norm_desc != raw_desc:
            corrections.append("Collapsed extra whitespace in description")

        raw_cat = str(r.get("category") or "").strip()
        norm_cat = raw_cat
        if not norm_cat and norm_desc:
            lower_desc = norm_desc.lower()
            for kw, suggested in MERCHANT_CATEGORY_RULES.items():
                if kw in lower_desc:
                    norm_cat = suggested
                    corrections.append(f"Auto-categorized as '{suggested}'")
                    break
            if not norm_cat:
                norm_cat = "Uncategorized"
                warnings.append("Missing category; defaulted to 'Uncategorized'")

        if norm_date and norm_amt is not None and norm_desc:
            sig = f"{norm_date}|{norm_amt:.2f}|{norm_desc.lower()}"
            if sig in seen_sigs:
                warnings.append("Potential duplicate transaction detected in batch or ledger")
            else:
                seen_sigs.add(sig)

        if errors:
            status = "error"
            error_count += 1
        elif warnings:
            status = "warning"
            warning_count += 1
            ready_count += 1
        else:
            status = "valid"
            ready_count += 1

        if corrections:
            corrected_count += 1

        preview_rows.append(
            {
                "row_number": idx,
                "status": status,
                "normalized": {
                    "date": norm_date,
                    "amount": norm_amt,
                    "description": norm_desc,
                    "category": norm_cat,
                },
                "errors": errors,
                "warnings": warnings,
                "corrections": corrections,
            }
        )

    return {
        "total_rows": len(rows),
        "ready_to_import_count": ready_count,
        "valid_clean_count": ready_count - warning_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "auto_corrected_count": corrected_count,
        "can_commit_all": error_count == 0 and len(rows) > 0,
        "rows": preview_rows,
    }
