"""
REST endpoints for Spending Trend Heatmap Visualization (#116).
"""

from flask import Blueprint, jsonify, request
from app.services.spending_heatmap import build_spending_heatmap

spending_heatmap_bp = Blueprint("spending_heatmap", __name__, url_prefix="/api/analytics")


@spending_heatmap_bp.route("/spending-heatmap", methods=["POST"])
def get_spending_heatmap():
    body = request.get_json(silent=True) or {}
    txs = body.get("transactions", [])
    return jsonify(build_spending_heatmap(txs)), 200
