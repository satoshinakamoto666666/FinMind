"""
REST endpoints for database index inspection & EXPLAIN QUERY PLAN analysis (#128).
"""

from flask import Blueprint, jsonify
from app.services.query_optimizer import RECOMMENDED_INDEXES

query_opt_bp = Blueprint("query_optimizer", __name__, url_prefix="/api/db")


@query_opt_bp.route("/indexes", methods=["GET"])
def get_recommended_indexes():
    return jsonify({"recommended_indexes": RECOMMENDED_INDEXES, "count": len(RECOMMENDED_INDEXES)}), 200
