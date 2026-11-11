"""
Spending Trend Heatmap Visualization Engine (#116).

Generates calendar heatmaps (intensity levels 0..4 based on spend quantiles),
day-of-week distribution matrices, category heat grids, and peak spending hotspots.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from typing import Any

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = q * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(sorted_vals[lo])
    return float(sorted_vals[lo] * (1.0 - (idx - lo)) + sorted_vals[hi] * (idx - lo))


def build_spending_heatmap(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    daily_totals: dict[str, float] = defaultdict(float)
    daily_counts: dict[str, int] = defaultdict(int)
    weekday_totals: dict[str, float] = {d: 0.0 for d in WEEKDAYS}
    weekday_counts: dict[str, int] = {d: 0 for d in WEEKDAYS}
    category_weekday: dict[str, dict[str, float]] = defaultdict(lambda: {d: 0.0 for d in WEEKDAYS})

    for tx in transactions:
        amt = float(tx.get("amount", 0.0) or 0.0)
        if amt <= 0:
            continue
        raw_date = str(tx.get("date", "")).strip()[:10]
        if not raw_date:
            continue
        try:
            dt = datetime.strptime(raw_date, "%Y-%m-%d")
        except ValueError:
            continue

        day_key = dt.strftime("%Y-%m-%d")
        wday = WEEKDAYS[dt.weekday()]
        cat = str(tx.get("category", "Uncategorized")).strip()

        daily_totals[day_key] += amt
        daily_counts[day_key] += 1
        weekday_totals[wday] += amt
        weekday_counts[wday] += 1
        category_weekday[cat][wday] = round(category_weekday[cat][wday] + amt, 2)

    non_zero_days = sorted(v for v in daily_totals.values() if v > 0)
    q25 = _quantile(non_zero_days, 0.25)
    q50 = _quantile(non_zero_days, 0.50)
    q75 = _quantile(non_zero_days, 0.75)

    def _intensity(val: float) -> int:
        if val <= 0:
            return 0
        if val <= q25:
            return 1
        if val <= q50:
            return 2
        if val <= q75:
            return 3
        return 4

    calendar_cells = []
    for day_key in sorted(daily_totals.keys()):
        amt = round(daily_totals[day_key], 2)
        calendar_cells.append(
            {
                "date": day_key,
                "amount": amt,
                "transaction_count": daily_counts[day_key],
                "intensity": _intensity(amt),
            }
        )

    weekday_summary = [
        {
            "weekday": w,
            "total_spend": round(weekday_totals[w], 2),
            "transaction_count": weekday_counts[w],
        }
        for w in WEEKDAYS
    ]

    highest_day = max(calendar_cells, key=lambda c: c["amount"]) if calendar_cells else None
    highest_weekday = max(weekday_summary, key=lambda w: w["total_spend"]) if calendar_cells else None

    return {
        "active_days_count": len(calendar_cells),
        "total_spend": round(sum(daily_totals.values()), 2),
        "thresholds": {
            "q25": round(q25, 2),
            "q50": round(q50, 2),
            "q75": round(q75, 2),
        },
        "calendar_heatmap": calendar_cells,
        "weekday_heatmap": weekday_summary,
        "category_weekday_matrix": dict(category_weekday),
        "hotspots": {
            "peak_date": highest_day,
            "peak_weekday": highest_weekday,
        },
    }
