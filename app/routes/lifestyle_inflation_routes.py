"""
REST endpoints for Lifestyle Inflation Detection Insights (#118).
"""

from flask import Blueprint, jsonify, request
from app.services.lifestyle_inflation import detect_lifestyle_inflation

lifestyle_inflation_bp = Blueprint("lifestyle_inflation", __name__, url_prefix="/api/insights")


@lifestyle_inflation_bp.route("/lifestyle-inflation", methods=["POST"])
def analyze_lifestyle_inflation():
    body = request.get_json(silent=True) or {}
    snapshots = body.get("monthly_snapshots", [])
    return jsonify(detect_lifestyle_inflation(snapshots)), 200
