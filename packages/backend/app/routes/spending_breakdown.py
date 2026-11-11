"""
REST endpoints for Essential vs Discretionary spending breakdown (#120).
"""

from flask import Blueprint, jsonify, request
from app.services.spending_breakdown import compute_spending_breakdown

spending_breakdown_bp = Blueprint("spending_breakdown", __name__, url_prefix="/api/expenses")


@spending_breakdown_bp.route("/spending-breakdown", methods=["POST"])
def get_spending_breakdown():
    body = request.get_json(silent=True) or {}
    report = compute_spending_breakdown(
        expenses=body.get("expenses", []),
        monthly_net_income=float(body.get("monthly_net_income", 0.0)),
        custom_overrides=body.get("custom_overrides"),
    )
    return jsonify(report), 200
