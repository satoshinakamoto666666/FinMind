"""
Savings opportunity detection engine for FinMind (#119).
Analyzes expense & subscription patterns across 5 rules:
1. Duplicate / overlapping subscriptions
2. Category overspend relative to historical baseline / targets
3. High-frequency small discretionary purchases ("latte factor")
4. Weekend discretionary spending surges
5. Uninvested idle cash drag
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any


ESSENTIAL_CATEGORIES = {"rent", "mortgage", "utilities", "healthcare", "groceries", "insurance", "taxes"}


def detect_savings_opportunities(
    expenses: list[dict[str, Any]],
    subscriptions: list[dict[str, Any]] | None = None,
    category_baselines: dict[str, float] | None = None,
    idle_cash_balance: float = 0.0,
    high_yield_apy: float = 0.045,
) -> dict[str, Any]:
    opportunities: list[dict[str, Any]] = []
    subscriptions = subscriptions or []
    category_baselines = category_baselines or {}

    # Rule 1: Duplicate or overlapping subscriptions in the same service group
    subs_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sub in subscriptions:
        if not sub.get("active", True):
            continue
        group = str(sub.get("category") or sub.get("group") or "streaming").lower()
        subs_by_group[group].append(sub)

    for group, group_subs in subs_by_group.items():
        if len(group_subs) >= 2:
            sorted_subs = sorted(group_subs, key=lambda s: float(s.get("monthly_cost", 0.0)))
            redundant_cost = sum(float(s.get("monthly_cost", 0.0)) for s in sorted_subs[:-1])
            if redundant_cost > 0:
                names = [str(s.get("name", "Subscription")) for s in sorted_subs]
                opportunities.append(
                    {
                        "rule_id": "duplicate_subscriptions",
                        "title": f"Consolidate overlapping {group} subscriptions",
                        "description": f"Detected {len(group_subs)} active {group} plans ({', '.join(names)}).",
                        "estimated_monthly_savings": round(redundant_cost, 2),
                        "estimated_annual_savings": round(redundant_cost * 12.0, 2),
                        "confidence": "high",
                    }
                )

    # Rule 2: Category overspend vs historical baseline
    spend_by_cat: dict[str, float] = defaultdict(float)
    for exp in expenses:
        cat = str(exp.get("category", "uncategorized")).lower()
        spend_by_cat[cat] += float(exp.get("amount", 0.0))

    for cat, current_spend in spend_by_cat.items():
        baseline = float(category_baselines.get(cat, 0.0))
        if baseline > 0 and current_spend > baseline * 1.20 and cat not in ESSENTIAL_CATEGORIES:
            excess = current_spend - baseline
            opportunities.append(
                {
                    "rule_id": "category_overspend",
                    "title": f"Reduce {cat.title()} overspending toward baseline",
                    "description": f"{cat.title()} spend (${current_spend:.2f}) is {((current_spend / baseline - 1) * 100):.0f}% above baseline (${baseline:.2f}).",
                    "estimated_monthly_savings": round(excess * 0.6, 2),
                    "estimated_annual_savings": round(excess * 0.6 * 12.0, 2),
                    "confidence": "medium",
                }
            )

    # Rule 3: High-frequency small discretionary purchases (<=$15, >=5 occurrences)
    micro_txs = [
        float(e.get("amount", 0.0))
        for e in expenses
        if 0 < float(e.get("amount", 0.0)) <= 15.0
        and str(e.get("category", "")).lower() not in ESSENTIAL_CATEGORIES
    ]
    if len(micro_txs) >= 5:
        micro_total = sum(micro_txs)
        saveable = round(micro_total * 0.4, 2)
        opportunities.append(
            {
                "rule_id": "high_frequency_micro_spend",
                "title": "Curb frequent small impulse purchases",
                "description": f"{len(micro_txs)} small discretionary transactions totaled ${micro_total:.2f}.",
                "estimated_monthly_savings": saveable,
                "estimated_annual_savings": round(saveable * 12.0, 2),
                "confidence": "medium",
            }
        )

    # Rule 4: Weekend discretionary surge
    weekend_spend = 0.0
    weekday_spend = 0.0
    for exp in expenses:
        cat = str(exp.get("category", "")).lower()
        if cat in ESSENTIAL_CATEGORIES:
            continue
        raw_date = exp.get("date")
        if not raw_date:
            continue
        dt = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00")) if isinstance(raw_date, str) else raw_date
        if dt.weekday() >= 5:
            weekend_spend += float(exp.get("amount", 0.0))
        else:
            weekday_spend += float(exp.get("amount", 0.0))

    if weekend_spend > 0 and weekend_spend > weekday_spend * 0.75:
        surge_savings = round(weekend_spend * 0.25, 2)
        opportunities.append(
            {
                "rule_id": "weekend_spending_surge",
                "title": "Set a weekend discretionary spending cap",
                "description": f"Weekend discretionary spending reached ${weekend_spend:.2f}.",
                "estimated_monthly_savings": surge_savings,
                "estimated_annual_savings": round(surge_savings * 12.0, 2),
                "confidence": "medium",
            }
        )

    # Rule 5: Idle cash yield opportunity
    if idle_cash_balance >= 2000.0 and high_yield_apy > 0:
        annual_yield = round(idle_cash_balance * high_yield_apy, 2)
        monthly_yield = round(annual_yield / 12.0, 2)
        opportunities.append(
            {
                "rule_id": "idle_cash_yield",
                "title": "Move idle cash buffer into high-yield savings",
                "description": f"${idle_cash_balance:,.2f} in low-yield checking can earn {high_yield_apy * 100:.1f}% APY.",
                "estimated_monthly_savings": monthly_yield,
                "estimated_annual_savings": annual_yield,
                "confidence": "high",
            }
        )

    opportunities.sort(key=lambda o: o["estimated_monthly_savings"], reverse=True)
    total_monthly = round(sum(o["estimated_monthly_savings"] for o in opportunities), 2)
    total_annual = round(sum(o["estimated_annual_savings"] for o in opportunities), 2)

    return {
        "opportunities": opportunities,
        "opportunities_count": len(opportunities),
        "total_estimated_monthly_savings": total_monthly,
        "total_estimated_annual_savings": total_annual,
    }
