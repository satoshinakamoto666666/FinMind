"""
Reminder Reliability Tracking & Delivery Metrics Engine (#123).

Tracks multi-channel reminder delivery outcomes (email, sms, push, in_app, webhook),
computes latency percentiles (p50, p95, mean), delivery & acknowledgment rates,
failure reason breakdowns, and SLA status classification.
"""

from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

VALID_CHANNELS = {"email", "sms", "push", "in_app", "webhook"}
VALID_STATUSES = {"queued", "sent", "delivered", "acknowledged", "bounced", "failed"}
SUCCESS_STATUSES = {"delivered", "acknowledged"}
FAILURE_STATUSES = {"bounced", "failed"}


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(float(sorted_vals[0]), 2)
    idx = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return round(float(sorted_vals[lo]), 2)
    weight = idx - lo
    return round(float(sorted_vals[lo] * (1.0 - weight) + sorted_vals[hi] * weight), 2)


class ReminderReliabilityTracker:
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def clear(self) -> None:
        self._events.clear()

    def record_event(
        self,
        reminder_id: str,
        channel: str,
        status: str,
        latency_ms: float = 0.0,
        failure_reason: str | None = None,
        user_id: str = "1",
    ) -> dict[str, Any]:
        ch = channel.strip().lower()
        st = status.strip().lower()
        if ch not in VALID_CHANNELS:
            raise ValueError(f"Unsupported channel: {channel}")
        if st not in VALID_STATUSES:
            raise ValueError(f"Unsupported delivery status: {status}")

        entry = {
            "reminder_id": str(reminder_id),
            "user_id": str(user_id),
            "channel": ch,
            "status": st,
            "latency_ms": max(0.0, float(latency_ms)),
            "failure_reason": failure_reason.strip() if failure_reason else None,
        }
        self._events.append(entry)
        return entry

    def compute_summary(self, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        rows = events if events is not None else self._events
        total = len(rows)
        if total == 0:
            return {
                "total_dispatches": 0,
                "delivered_count": 0,
                "acknowledged_count": 0,
                "failed_count": 0,
                "delivery_rate_pct": 100.0,
                "ack_rate_pct": 0.0,
                "sla_status": "healthy",
                "latency_ms": {"p50": 0.0, "p95": 0.0, "mean": 0.0},
                "failure_reasons": {},
                "by_channel": {},
            }

        delivered = 0
        acked = 0
        failed = 0
        latencies: list[float] = []
        failure_reasons: dict[str, int] = defaultdict(int)
        channel_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for r in rows:
            st = str(r.get("status", "")).lower()
            ch = str(r.get("channel", "email")).lower()
            lat = float(r.get("latency_ms", 0.0))
            channel_buckets[ch].append(r)

            if st in SUCCESS_STATUSES:
                delivered += 1
                if lat > 0:
                    latencies.append(lat)
            if st == "acknowledged":
                acked += 1
            if st in FAILURE_STATUSES:
                failed += 1
                reason = r.get("failure_reason") or "unspecified_error"
                failure_reasons[str(reason)] += 1

        latencies.sort()
        delivery_rate = round((delivered / total) * 100.0, 2)
        ack_rate = round((acked / delivered) * 100.0, 2) if delivered > 0 else 0.0

        if delivery_rate >= 98.0:
            sla_status = "healthy"
        elif delivery_rate >= 90.0:
            sla_status = "degraded"
        else:
            sla_status = "critical"

        by_channel: dict[str, Any] = {}
        for ch, ch_rows in sorted(channel_buckets.items()):
            ch_total = len(ch_rows)
            ch_deliv = sum(1 for x in ch_rows if str(x.get("status", "")).lower() in SUCCESS_STATUSES)
            ch_fail = sum(1 for x in ch_rows if str(x.get("status", "")).lower() in FAILURE_STATUSES)
            ch_lats = sorted(
                float(x.get("latency_ms", 0.0))
                for x in ch_rows
                if str(x.get("status", "")).lower() in SUCCESS_STATUSES and float(x.get("latency_ms", 0.0)) > 0
            )
            by_channel[ch] = {
                "total": ch_total,
                "delivered": ch_deliv,
                "failed": ch_fail,
                "delivery_rate_pct": round((ch_deliv / ch_total) * 100.0, 2) if ch_total else 0.0,
                "p95_latency_ms": _percentile(ch_lats, 95.0),
            }

        return {
            "total_dispatches": total,
            "delivered_count": delivered,
            "acknowledged_count": acked,
            "failed_count": failed,
            "delivery_rate_pct": delivery_rate,
            "ack_rate_pct": ack_rate,
            "sla_status": sla_status,
            "latency_ms": {
                "p50": _percentile(latencies, 50.0),
                "p95": _percentile(latencies, 95.0),
                "mean": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            },
            "failure_reasons": dict(failure_reasons),
            "by_channel": by_channel,
        }


reliability_tracker = ReminderReliabilityTracker()
