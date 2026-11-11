"""
REST endpoints for viewing, trusting, and revoking user devices (#125).
"""

from flask import Blueprint, jsonify, request
from app.services.device_trust import device_trust_manager

device_trust_bp = Blueprint("device_trust", __name__, url_prefix="/api/devices")


@device_trust_bp.route("", methods=["GET"])
def list_user_devices():
    user_id = request.args.get("user_id", "1")
    return jsonify({"devices": device_trust_manager.list_devices(user_id)}), 200


@device_trust_bp.route("/recognize", methods=["POST"])
def recognize_device():
    body = request.get_json(silent=True) or {}
    res = device_trust_manager.register_or_recognize(
        user_id=body.get("user_id", "1"),
        user_agent=body.get("user_agent", request.headers.get("User-Agent", "unknown")),
        ip_address=body.get("ip_address", request.remote_addr or "127.0.0.1"),
        platform=body.get("platform", "web"),
        device_name=body.get("device_name"),
    )
    return jsonify(res), 200


@device_trust_bp.route("/<device_id>/trust", methods=["POST"])
def mark_device_trusted(device_id: str):
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id", "1")
    try:
        updated = device_trust_manager.trust_device(user_id, device_id)
        return jsonify(updated), 200
    except KeyError as err:
        return jsonify({"error": str(err)}), 404
    except PermissionError as err:
        return jsonify({"error": str(err)}), 403


@device_trust_bp.route("/<device_id>/revoke", methods=["POST"])
def mark_device_revoked(device_id: str):
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id", "1")
    try:
        updated = device_trust_manager.revoke_device(user_id, device_id)
        return jsonify(updated), 200
    except KeyError as err:
        return jsonify({"error": str(err)}), 404
