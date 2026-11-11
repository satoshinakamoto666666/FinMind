import io
import logging
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from ..services.gdpr import (
    anonymize_user_pii,
    cancel_account_deletion,
    execute_irreversible_deletion,
    generate_pii_export_dict,
    generate_pii_export_zip,
    list_gdpr_audit_logs,
    request_account_deletion,
)

bp = Blueprint("gdpr", __name__)
logger = logging.getLogger("finmind.gdpr")


def _client_meta() -> tuple[str | None, str | None]:
    ip = request.headers.get("X-Forwarded-For") or request.remote_addr
    ua = request.headers.get("User-Agent")
    return ip, ua


@bp.get("/export")
@jwt_required()
def export_user_pii():
    uid = int(get_jwt_identity())
    fmt = (request.args.get("format") or "json").strip().lower()
    ip, ua = _client_meta()
    try:
        if fmt == "zip":
            zip_bytes = generate_pii_export_zip(uid, ip_address=ip, user_agent=ua)
            return send_file(
                io.BytesIO(zip_bytes),
                mimetype="application/zip",
                as_attachment=True,
                download_name=f"finmind_gdpr_export_user_{uid}.zip",
            )
        if fmt != "json":
            return jsonify(error="unsupported format; use 'json' or 'zip'"), 400
        payload = generate_pii_export_dict(uid, ip_address=ip, user_agent=ua)
        return jsonify(payload), 200
    except LookupError:
        return jsonify(error="user not found"), 404


@bp.post("/delete/request")
@jwt_required()
def initiate_deletion():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    grace_days = data.get("grace_days", 30)
    reason = data.get("reason")
    ip, ua = _client_meta()
    try:
        result = request_account_deletion(
            uid=uid,
            password=password,
            grace_days=grace_days,
            reason=reason,
            ip_address=ip,
            user_agent=ua,
        )
        return jsonify(result), 201
    except LookupError:
        return jsonify(error="user not found"), 404
    except PermissionError as exc:
        return jsonify(error=str(exc)), 401
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@bp.post("/delete/cancel")
@jwt_required()
def cancel_deletion():
    uid = int(get_jwt_identity())
    ip, ua = _client_meta()
    try:
        result = cancel_account_deletion(uid=uid, ip_address=ip, user_agent=ua)
        return jsonify(result), 200
    except LookupError:
        return jsonify(error="user not found"), 404
    except ValueError as exc:
        return jsonify(error=str(exc)), 404


@bp.post("/delete/confirm")
@bp.delete("/delete")
@jwt_required()
def confirm_irreversible_deletion():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    password = data.get("password")
    token = data.get("confirmation_token")
    ip, ua = _client_meta()
    try:
        result = execute_irreversible_deletion(
            uid=uid,
            password=password,
            confirmation_token=token,
            ip_address=ip,
            user_agent=ua,
        )
        logger.info("Executed GDPR irreversible deletion for uid=%s", uid)
        return jsonify(result), 200
    except LookupError:
        return jsonify(error="user not found"), 404
    except PermissionError as exc:
        return jsonify(error=str(exc)), 401


@bp.post("/anonymize")
@jwt_required()
def anonymize_pii():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    ip, ua = _client_meta()
    try:
        result = anonymize_user_pii(
            uid=uid, password=password, ip_address=ip, user_agent=ua
        )
        return jsonify(result), 200
    except LookupError:
        return jsonify(error="user not found"), 404
    except PermissionError as exc:
        return jsonify(error=str(exc)), 401


@bp.get("/audit-logs")
@jwt_required()
def get_audit_logs():
    uid = int(get_jwt_identity())
    subject_hash = request.args.get("subject_hash")
    logs = list_gdpr_audit_logs(uid=uid, subject_hash=subject_hash)
    return jsonify(audit_logs=logs, count=len(logs)), 200
