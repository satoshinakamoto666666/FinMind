"""
Lifestyle Inflation Detection Insights Engine (#118).

Detects rising discretionary expenses over time ("lifestyle creep") by comparing
baseline vs recent periods across income growth, discretionary spending growth,
savings rate erosion, and category-level drivers.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

ESSENTIAL_CATEGORIES = {
    "housing",
    "rent",
    "mortgage",
    "utilities",
    "groceries",
    "healthcare",
    "insurance",
    "transportation",
    "debt_repayment",
}


def detect_lifestyle_inflation(monthly_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analyze chronological monthly snapshots:
    [{"month": "2026-01", "income": 5000.0, "categories": {"Dining": 300, "Rent": 1500, ...}}, ...]
    """
    if len(monthly_snapshots) < 2:
        return {
            "lifestyle_inflation_detected": False,
            "severity": "none",
            "summary": "At least 2 monthly snapshots are required to evaluate lifestyle inflation.",
            "category_drivers": [],
        }

    ordered = sorted(monthly_snapshots, key=lambda m: str(m.get("month", "")))
    mid = max(1, len(ordered) // 2)
    baseline_slice = ordered[:mid]
    recent_slice = ordered[mid:]

    def _avg_metrics(snapshots: list[dict[str, Any]]) -> tuple[float, float, float, dict[str, float]]:
        n = len(snapshots)
        total_inc = 0.0
        total_ess = 0.0
        total_disc = 0.0
        cat_sums: dict[str, float] = defaultdict(float)

        for s in snapshots:
            total_inc += float(s.get("income", 0.0))
            cats = s.get("categories", {}) or {}
            for cat, amt in cats.items():
                val = float(amt)
                cat_sums[cat] += val
                if cat.strip().lower() in ESSENTIAL_CATEGORIES:
                    total_ess += val
                else:
                    total_disc += val

        avg_cats = {k: v / n for k, v in cat_sums.items()}
        return total_inc / n, total_ess / n, total_disc / n, avg_cats

    base_inc, base_ess, base_disc, base_cats = _avg_metrics(baseline_slice)
    rec_inc, rec_ess, rec_disc, rec_cats = _avg_metrics(recent_slice)

    inc_growth_pct = round(((rec_inc - base_inc) / base_inc) * 100.0, 2) if base_inc > 0 else 0.0
    disc_growth_pct = round(((rec_disc - base_disc) / base_disc) * 100.0, 2) if base_disc > 0 else 0.0

    base_savings_rate = round(((base_inc - base_ess - base_disc) / base_inc) * 100.0, 2) if base_inc > 0 else 0.0
    rec_savings_rate = round(((rec_inc - rec_ess - rec_disc) / rec_inc) * 100.0, 2) if rec_inc > 0 else 0.0
    savings_rate_delta = round(rec_savings_rate - base_savings_rate, 2)

    inc_delta = rec_inc - base_inc
    disc_delta = rec_disc - base_disc
    income_absorbed_by_creep_pct = (
        round((disc_delta / inc_delta) * 100.0, 2) if inc_delta > 0 and disc_delta > 0 else 0.0
    )

    drivers: list[dict[str, Any]] = []
    all_cats = set(base_cats.keys()) | set(rec_cats.keys())
    for cat in all_cats:
        if cat.strip().lower() in ESSENTIAL_CATEGORIES:
            continue
        b_val = base_cats.get(cat, 0.0)
        r_val = rec_cats.get(cat, 0.0)
        diff = round(r_val - b_val, 2)
        if diff > 10.0:
            pct = round((diff / b_val) * 100.0, 2) if b_val > 0 else 100.0
            drivers.append(
                {
                    "category": cat,
                    "baseline_monthly_avg": round(b_val, 2),
                    "recent_monthly_avg": round(r_val, 2),
                    "monthly_increase": diff,
                    "annualized_impact": round(diff * 12.0, 2),
                    "growth_pct": pct,
                }
            )

    drivers.sort(key=lambda d: d["monthly_increase"], reverse=True)

    detected = (disc_growth_pct >= 15.0 and disc_growth_pct > inc_growth_pct + 5.0) or (
        inc_delta > 0 and income_absorbed_by_creep_pct >= 50.0
    )

    if not detected:
        severity = "none"
    elif disc_growth_pct >= 35.0 or income_absorbed_by_creep_pct >= 80.0:
        severity = "high"
    else:
        severity = "moderate"

    monthly_creep_amount = round(max(0.0, disc_delta), 2)

    return {
        "lifestyle_inflation_detected": detected,
        "severity": severity,
        "baseline_income_avg": round(base_inc, 2),
        "recent_income_avg": round(rec_inc, 2),
        "income_growth_pct": inc_growth_pct,
        "baseline_discretionary_avg": round(base_disc, 2),
        "recent_discretionary_avg": round(rec_disc, 2),
        "discretionary_growth_pct": disc_growth_pct,
        "baseline_savings_rate_pct": base_savings_rate,
        "recent_savings_rate_pct": rec_savings_rate,
        "savings_rate_delta_pct": savings_rate_delta,
        "income_absorbed_by_creep_pct": income_absorbed_by_creep_pct,
        "monthly_creep_amount": monthly_creep_amount,
        "annualized_creep_cost": round(monthly_creep_amount * 12.0, 2),
        "category_drivers": drivers,
    }
