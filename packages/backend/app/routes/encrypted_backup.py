"""
REST endpoints for encrypted backup creation and verified restoration (#126).
"""

from flask import Blueprint, jsonify, request
from app.services.encrypted_backup import create_encrypted_backup, restore_encrypted_backup

backup_bp = Blueprint("encrypted_backup", __name__, url_prefix="/api/backup")


@backup_bp.route("/export-encrypted", methods=["POST"])
def export_encrypted():
    body = request.get_json(silent=True) or {}
    records = body.get("records", [])
    passphrase = body.get("passphrase", "")
    fmt = body.get("format", "json")
    try:
        envelope = create_encrypted_backup(records, passphrase=passphrase, fmt=fmt)
        return jsonify(envelope), 200
    except ValueError as err:
        return jsonify({"error": str(err)}), 400


@backup_bp.route("/restore-encrypted", methods=["POST"])
def restore_encrypted():
    body = request.get_json(silent=True) or {}
    envelope = body.get("envelope", {})
    passphrase = body.get("passphrase", "")
    try:
        plaintext = restore_encrypted_backup(envelope, passphrase=passphrase)
        return jsonify({"restored": plaintext.decode("utf-8"), "format": envelope.get("format", "json")}), 200
    except PermissionError as err:
        return jsonify({"error": str(err)}), 403
    except (ValueError, KeyError) as err:
        return jsonify({"error": str(err)}), 400
