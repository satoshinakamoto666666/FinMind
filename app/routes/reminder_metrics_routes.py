"""
REST API routes for Reminder Reliability Tracking & Delivery Metrics (#123).
"""

from flask import Blueprint, jsonify, request
from app.services.reminder_reliability import reliability_tracker

reminder_metrics_bp = Blueprint("reminder_metrics", __name__, url_prefix="/api/reminders/metrics")


@reminder_metrics_bp.route("/record", methods=["POST"])
def record_delivery_event():
    body = request.get_json(silent=True) or {}
    try:
        ev = reliability_tracker.record_event(
            reminder_id=body.get("reminder_id", "rem-1"),
            channel=body.get("channel", "email"),
            status=body.get("status", "delivered"),
            latency_ms=float(body.get("latency_ms", 120.0)),
            failure_reason=body.get("failure_reason"),
            user_id=body.get("user_id", "1"),
        )
        return jsonify(ev), 201
    except ValueError as err:
        return jsonify({"error": str(err)}), 400


@reminder_metrics_bp.route("/summary", methods=["GET", "POST"])
def get_reliability_summary():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        events = body.get("events", [])
        return jsonify(reliability_tracker.compute_summary(events)), 200
    return jsonify(reliability_tracker.compute_summary()), 200
