"""
REST endpoints for Notification Priority & Grouping System (#122).
"""

from flask import Blueprint, jsonify, request
from app.services.notification_grouping import group_and_prioritize_notifications

notification_grouping_bp = Blueprint("notification_grouping", __name__, url_prefix="/api/notifications")


@notification_grouping_bp.route("/group", methods=["POST"])
def group_notifications_endpoint():
    body = request.get_json(silent=True) or {}
    notifications = body.get("notifications", [])
    dedup_window = int(body.get("dedup_window_seconds", 300))
    return jsonify(group_and_prioritize_notifications(notifications, dedup_window)), 200
