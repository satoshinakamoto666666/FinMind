"""
Essential vs Discretionary spending breakdown service for FinMind (#120).
Classifies transactions into Essential, Discretionary, and Savings/Debt,
evaluates 50/30/20 budget alignment, and surfaces top categories per tier.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


ESSENTIAL_KEYWORDS = {
    "rent",
    "mortgage",
    "housing",
    "groceries",
    "utilities",
    "electricity",
    "water",
    "gas",
    "internet",
    "healthcare",
    "medical",
    "pharmacy",
    "insurance",
    "transport",
    "commute",
    "tuition",
    "childcare",
    "taxes",
}

SAVINGS_KEYWORDS = {
    "savings",
    "investment",
    "retirement",
    "401k",
    "ira",
    "emergency_fund",
    "debt_payoff",
}


def classify_category(
    category: str,
    custom_overrides: dict[str, str] | None = None,
) -> str:
    clean = str(category or "uncategorized").strip().lower()
    if custom_overrides and clean in {k.lower(): v for k, v in custom_overrides.items()}:
        return {k.lower(): v for k, v in custom_overrides.items()}[clean]
    for kw in SAVINGS_KEYWORDS:
        if kw in clean:
            return "savings"
    for kw in ESSENTIAL_KEYWORDS:
        if kw in clean:
            return "essential"
    return "discretionary"


def compute_spending_breakdown(
    expenses: list[dict[str, Any]],
    monthly_net_income: float = 0.0,
    custom_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    totals = {"essential": 0.0, "discretionary": 0.0, "savings": 0.0}
    cat_map: dict[str, dict[str, float]] = {
        "essential": defaultdict(float),
        "discretionary": defaultdict(float),
        "savings": defaultdict(float),
    }

    for exp in expenses:
        amt = float(exp.get("amount", 0.0))
        if amt <= 0:
            continue
        cat = str(exp.get("category", "Uncategorized")).strip()
        bucket = exp.get("priority_type") or classify_category(cat, custom_overrides=custom_overrides)
        if bucket not in totals:
            bucket = "discretionary"
        totals[bucket] += amt
        cat_map[bucket][cat] += amt

    total_outflow = sum(totals.values())
    denom = total_outflow if total_outflow > 0 else 1.0

    pct_of_spend = {k: round((v / denom) * 100.0, 2) if total_outflow > 0 else 0.0 for k, v in totals.items()}

    def _top_cats(bucket: str) -> list[dict[str, Any]]:
        items = sorted(cat_map[bucket].items(), key=lambda kv: kv[1], reverse=True)
        return [{"category": k, "amount": round(v, 2)} for k, v in items]

    rule_50_30_20 = None
    if monthly_net_income > 0:
        ess_inc_pct = round((totals["essential"] / monthly_net_income) * 100.0, 2)
        disc_inc_pct = round((totals["discretionary"] / monthly_net_income) * 100.0, 2)
        sav_inc_pct = round(((monthly_net_income - totals["essential"] - totals["discretionary"]) / monthly_net_income) * 100.0, 2)
        rule_50_30_20 = {
            "essential_pct_of_income": ess_inc_pct,
            "discretionary_pct_of_income": disc_inc_pct,
            "implied_savings_pct_of_income": sav_inc_pct,
            "discretionary_within_30_pct_target": disc_inc_pct <= 30.0,
            "essential_within_50_pct_target": ess_inc_pct <= 50.0,
        }

    return {
        "total_outflow": round(total_outflow, 2),
        "totals": {k: round(v, 2) for k, v in totals.items()},
        "percentages": pct_of_spend,
        "top_categories": {
            "essential": _top_cats("essential"),
            "discretionary": _top_cats("discretionary"),
            "savings": _top_cats("savings"),
        },
        "rule_50_30_20": rule_50_30_20,
    }
