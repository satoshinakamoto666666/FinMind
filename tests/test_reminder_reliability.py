import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.reminder_reliability import ReminderReliabilityTracker


def test_healthy_sla_and_latency_percentiles():
    tracker = ReminderReliabilityTracker()
    for i in range(99):
        tracker.record_event(f"r-{i}", "email", "delivered", latency_ms=100 + i)
    tracker.record_event("r-99", "email", "acknowledged", latency_ms=200)
    summary = tracker.compute_summary()
    assert summary["total_dispatches"] == 100
    assert summary["delivered_count"] == 100
    assert summary["acknowledged_count"] == 1
    assert summary["delivery_rate_pct"] == 100.0
    assert summary["sla_status"] == "healthy"
    assert summary["latency_ms"]["p50"] > 140.0
    assert summary["latency_ms"]["p95"] >= 190.0


def test_degraded_and_critical_sla_classification():
    tracker = ReminderReliabilityTracker()
    events = [
        {"reminder_id": "1", "channel": "sms", "status": "delivered", "latency_ms": 80},
        {"reminder_id": "2", "channel": "sms", "status": "delivered", "latency_ms": 90},
        {"reminder_id": "3", "channel": "sms", "status": "failed", "failure_reason": "carrier_timeout"},
    ]
    res = tracker.compute_summary(events)
    assert res["delivery_rate_pct"] == 66.67
    assert res["sla_status"] == "critical"
    assert res["failure_reasons"]["carrier_timeout"] == 1


def test_per_channel_breakdown():
    tracker = ReminderReliabilityTracker()
    tracker.record_event("1", "push", "delivered", latency_ms=45)
    tracker.record_event("2", "webhook", "bounced", failure_reason="http_502")
    res = tracker.compute_summary()
    assert res["by_channel"]["push"]["delivery_rate_pct"] == 100.0
    assert res["by_channel"]["webhook"]["delivery_rate_pct"] == 0.0
    assert res["by_channel"]["webhook"]["failed"] == 1


def test_rejects_invalid_channel_or_status():
    tracker = ReminderReliabilityTracker()
    with pytest.raises(ValueError):
        tracker.record_event("1", "carrier_pigeon", "delivered")
    with pytest.raises(ValueError):
        tracker.record_event("1", "email", "unknown_state")


def test_empty_summary_returns_healthy_defaults():
    tracker = ReminderReliabilityTracker()
    res = tracker.compute_summary([])
    assert res["total_dispatches"] == 0
    assert res["sla_status"] == "healthy"
