"""
Category overspend early warning system for FinMind (#117).
Computes daily spending velocity, end-of-month projections, and safe remaining daily
allowance per category, firing severity-ranked early alerts (warning / critical / over_budget).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


SEVERITY_ORDER = {"over_budget": 3, "critical": 2, "warning": 1, "ok": 0}


def evaluate_category_early_warnings(
    expenses: list[dict[str, Any]],
    budgets: dict[str, float],
    day_of_month: int = 15,
    days_in_month: int = 30,
    warning_threshold_pct: float = 80.0,
) -> dict[str, Any]:
    elapsed_days = max(1, min(day_of_month, days_in_month))
    remaining_days = max(0, days_in_month - elapsed_days)

    spend_by_cat: dict[str, float] = defaultdict(float)
    for exp in expenses:
        cat = str(exp.get("category", "Uncategorized")).strip()
        spend_by_cat[cat] += float(exp.get("amount", 0.0))

    warnings: list[dict[str, Any]] = []
    for cat, limit_amt in budgets.items():
        if limit_amt <= 0:
            continue
        current = round(spend_by_cat.get(cat, 0.0), 2)
        used_pct = round((current / limit_amt) * 100.0, 2)
        daily_pace = current / elapsed_days
        projected_eom = round(daily_pace * days_in_month, 2)
        projected_pct = round((projected_eom / limit_amt) * 100.0, 2)
        remaining_budget = max(0.0, round(limit_amt - current, 2))
        safe_daily_allowance = round(remaining_budget / remaining_days, 2) if remaining_days > 0 else 0.0

        if current > limit_amt:
            severity = "over_budget"
        elif used_pct >= warning_threshold_pct or projected_eom > limit_amt * 1.50:
            severity = "critical"
        elif projected_eom > limit_amt:
            severity = "warning"
        else:
            severity = "ok"

        warnings.append(
            {
                "category": cat,
                "budget_limit": round(limit_amt, 2),
                "current_spend": current,
                "budget_used_pct": used_pct,
                "projected_month_end_spend": projected_eom,
                "projected_budget_pct": projected_pct,
                "remaining_budget": remaining_budget,
                "safe_daily_allowance": safe_daily_allowance,
                "severity": severity,
            }
        )

    warnings.sort(key=lambda w: (SEVERITY_ORDER[w["severity"]], w["projected_budget_pct"]), reverse=True)
    active_alerts = [w for w in warnings if w["severity"] != "ok"]

    return {
        "day_of_month": elapsed_days,
        "days_in_month": days_in_month,
        "active_alerts_count": len(active_alerts),
        "alerts": active_alerts,
        "all_categories": warnings,
    }
