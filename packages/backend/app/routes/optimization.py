"""
Flask middleware & diagnostic endpoints for API response compression & payload optimization (#129).
"""

from flask import Blueprint, jsonify, request
from app.services.payload_optimizer import (
    compress_payload,
    optimize_json_payload,
    serialize_minified_json,
)

optimization_bp = Blueprint("optimization", __name__, url_prefix="/api/optimization")


@optimization_bp.route("/preview", methods=["POST"])
def preview_payload_optimization():
    body = request.get_json(silent=True) or {}
    payload = body.get("payload", {})
    fields_param = body.get("fields")
    strip_nulls = bool(body.get("strip_nulls", True))
    min_size = int(body.get("min_size_bytes", 128))

    optimized = optimize_json_payload(payload, strip_nulls=strip_nulls, fields=fields_param)
    raw_bytes = serialize_minified_json(optimized)
    compressed_bytes, headers = compress_payload(
        raw_bytes,
        accept_encoding=request.headers.get("Accept-Encoding", "gzip"),
        min_size_bytes=min_size,
    )
    return jsonify(
        {
            "optimized_payload": optimized,
            "original_bytes": len(json.dumps(payload).encode("utf-8")),
            "minified_bytes": len(raw_bytes),
            "compressed_bytes": len(compressed_bytes),
            "headers": headers,
        }
    ), 200
