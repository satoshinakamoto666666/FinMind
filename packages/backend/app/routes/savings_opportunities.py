"""
REST endpoints for FinMind Savings Opportunity Detection Engine (#119).
"""

from flask import Blueprint, jsonify, request
from app.services.savings_opportunities import detect_savings_opportunities

savings_bp = Blueprint("savings_opportunities", __name__, url_prefix="/api/insights")


@savings_bp.route("/savings-opportunities", methods=["POST"])
def analyze_savings_opportunities():
    body = request.get_json(silent=True) or {}
    report = detect_savings_opportunities(
        expenses=body.get("expenses", []),
        subscriptions=body.get("subscriptions", []),
        category_baselines=body.get("category_baselines", {}),
        idle_cash_balance=float(body.get("idle_cash_balance", 0.0)),
        high_yield_apy=float(body.get("high_yield_apy", 0.045)),
    )
    return jsonify(report), 200
