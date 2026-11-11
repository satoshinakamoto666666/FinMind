"""
REST endpoints for smart dashboard & analytics cache telemetry and invalidation (#127).
"""

from flask import Blueprint, jsonify, request
from app.services.smart_cache import dashboard_cache

cache_bp = Blueprint("smart_cache", __name__, url_prefix="/api/cache")


@cache_bp.route("/metrics", methods=["GET"])
def get_cache_metrics():
    return jsonify(dashboard_cache.metrics()), 200


@cache_bp.route("/invalidate", methods=["POST"])
def invalidate_cache():
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    entity_type = body.get("entity_type", "expenses")
    tag = body.get("tag")

    if tag:
        evicted = dashboard_cache.invalidate_by_tag(tag)
    elif user_id is not None:
        evicted = dashboard_cache.invalidate_user_Mutation(user_id, entity_type=entity_type)
    else:
        return jsonify({"error": "user_id or tag is required"}), 400

    return jsonify({"evicted_entries": evicted, "metrics": dashboard_cache.metrics()}), 200
