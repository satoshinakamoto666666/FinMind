"""
REST endpoints for Category Overspend Early Warning System (#117).
"""

from flask import Blueprint, jsonify, request
from app.services.overspend_warning import evaluate_category_early_warnings

overspend_bp = Blueprint("overspend_warning", __name__, url_prefix="/api/budgets")


@overspend_bp.route("/early-warnings", methods=["POST"])
def check_early_warnings():
    body = request.get_json(silent=True) or {}
    report = evaluate_category_early_warnings(
        expenses=body.get("expenses", []),
        budgets=body.get("budgets", {}),
        day_of_month=int(body.get("day_of_month", 15)),
        days_in_month=int(body.get("days_in_month", 30)),
        warning_threshold_pct=float(body.get("warning_threshold_pct", 80.0)),
    )
    return jsonify(report), 200
