"""
Notification Priority & Grouping System (#122).

Scores incoming alerts across 4 priority levels (critical, high, medium, low),
deduplicates noisy alerts within a cooldown window, and groups related alerts
into collapsible notification bundles with human-readable summary headers.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

PRIORITY_WEIGHTS = {
    "critical": 100,
    "high": 75,
    "medium": 50,
    "low": 25,
}

EVENT_DEFAULT_PRIORITY = {
    "security_alert": "critical",
    "overdraft_risk": "critical",
    "fraud_suspected": "critical",
    "bill_overdue": "high",
    "budget_exceeded": "high",
    "bill_due_soon": "medium",
    "subscription_renewal": "medium",
    "budget_warning": "medium",
    "weekly_digest": "low",
    "savings_tip": "low",
}


def classify_priority(notification: dict[str, Any]) -> str:
    explicit = str(notification.get("priority", "")).strip().lower()
    if explicit in PRIORITY_WEIGHTS:
        base_prio = explicit
    else:
        ev_type = str(notification.get("event_type", "general")).strip().lower()
        base_prio = EVENT_DEFAULT_PRIORITY.get(ev_type, "low")

    amount = float(notification.get("amount", 0.0) or 0.0)
    if amount >= 5000.0:
        return "critical"
    if amount >= 1000.0 and PRIORITY_WEIGHTS[base_prio] < PRIORITY_WEIGHTS["high"]:
        return "high"
    return base_prio


def group_and_prioritize_notifications(
    notifications: list[dict[str, Any]],
    dedup_window_seconds: int = 300,
) -> dict[str, Any]:
    deduped: list[dict[str, Any]] = []
    last_seen_ts: dict[str, int] = {}
    suppressed_duplicates = 0

    sorted_input = sorted(notifications, key=lambda n: int(n.get("timestamp", 0)))
    for notif in sorted_input:
        ev_type = str(notif.get("event_type", "general")).strip().lower()
        entity_id = str(notif.get("entity_id", notif.get("category", "global"))).strip().lower()
        title = str(notif.get("title", "")).strip()
        ts = int(notif.get("timestamp", 0))
        dedup_key = f"{ev_type}:{entity_id}:{title}"

        if dedup_key in last_seen_ts and (ts - last_seen_ts[dedup_key]) <= dedup_window_seconds:
            suppressed_duplicates += 1
            continue

        last_seen_ts[dedup_key] = ts
        prio = classify_priority(notif)
        enriched = dict(notif)
        enriched["priority"] = prio
        enriched["priority_score"] = PRIORITY_WEIGHTS[prio]
        deduped.append(enriched)

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in deduped:
        cat = str(item.get("category") or item.get("event_type") or "general").strip().lower()
        buckets[cat].append(item)

    groups: list[dict[str, Any]] = []
    for cat, items in buckets.items():
        items.sort(key=lambda x: (x["priority_score"], int(x.get("timestamp", 0))), reverse=True)
        top_prio = items[0]["priority"]
        top_score = items[0]["priority_score"]
        latest_ts = max(int(x.get("timestamp", 0)) for x in items)
        unread_count = sum(1 for x in items if not x.get("read", False))

        if len(items) == 1:
            headline = items[0].get("title") or f"1 {cat} alert"
        else:
            headline = f"{len(items)} {cat.replace('_', ' ')} notifications ({top_prio} priority)"

        groups.append(
            {
                "group_key": cat,
                "headline": headline,
                "highest_priority": top_prio,
                "priority_score": top_score,
                "count": len(items),
                "unread_count": unread_count,
                "latest_timestamp": latest_ts,
                "collapsed": len(items) > 1 and top_prio != "critical",
                "items": items,
            }
        )

    groups.sort(key=lambda g: (g["priority_score"], g["latest_timestamp"], g["count"]), reverse=True)

    return {
        "total_input": len(notifications),
        "suppressed_duplicates": suppressed_duplicates,
        "total_active": len(deduped),
        "group_count": len(groups),
        "groups": groups,
    }
