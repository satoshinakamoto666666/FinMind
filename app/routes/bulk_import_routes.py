"""
REST endpoints for Bulk Import Validation & Preview (#115).
"""

from flask import Blueprint, jsonify, request
from app.services.bulk_import_validator import validate_and_preview_bulk_import

bulk_import_bp = Blueprint("bulk_import", __name__, url_prefix="/api/import")


@bulk_import_bp.route("/preview", methods=["POST"])
def preview_bulk_import():
    body = request.get_json(silent=True) or {}
    rows = body.get("rows", [])
    existing = set(body.get("existing_signatures", []))
    return jsonify(validate_and_preview_bulk_import(rows, existing)), 200
