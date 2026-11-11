from datetime import datetime
import json
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import LoginEvent, SecurityAlert, TrustedDevice
from ..services.login_anomaly import compute_device_fingerprint, extract_request_metadata

bp = Blueprint("security", __name__)


def _serialize_event(e: LoginEvent) -> dict:
    return {
        "id": e.id,
        "email": e.email,
        "ip_address": e.ip_address,
        "user_agent": e.user_agent,
        "device_fingerprint": e.device_fingerprint,
        "country_code": e.country_code,
        "success": e.success,
        "risk_score": e.risk_score,
        "is_suspicious": e.is_suspicious,
        "reasons": json.loads(e.reasons_json or "[]"),
        "created_at": e.created_at.isoformat(),
    }


def _serialize_alert(a: SecurityAlert) -> dict:
    return {
        "id": a.id,
        "login_event_id": a.login_event_id,
        "severity": a.severity,
        "alert_type": a.alert_type,
        "reasons": json.loads(a.reason_codes_json or "[]"),
        "message": a.message,
        "acknowledged": a.acknowledged,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "created_at": a.created_at.isoformat(),
    }


@bp.get("/login-history")
@jwt_required()
def login_history():
    uid = int(get_jwt_identity())
    limit = min(int(request.args.get("limit", 50)), 200)
    suspicious_only = request.args.get("suspicious_only", "false").lower() == "true"
    q = db.session.query(LoginEvent).filter(LoginEvent.user_id == uid)
    if suspicious_only:
        q = q.filter(LoginEvent.is_suspicious.is_(True))
    rows = q.order_by(LoginEvent.id.desc()).limit(limit).all()
    return jsonify([_serialize_event(r) for r in rows])


@bp.get("/alerts")
@bp.get("/anomalies")
@jwt_required()
def list_alerts():
    uid = int(get_jwt_identity())
    unack_only = request.args.get("unacknowledged_only", "false").lower() == "true"
    severity = (request.args.get("severity") or "").upper().strip()
    q = db.session.query(SecurityAlert).filter(SecurityAlert.user_id == uid)
    if unack_only:
        q = q.filter(SecurityAlert.acknowledged.is_(False))
    if severity:
        q = q.filter(SecurityAlert.severity == severity)
    rows = q.order_by(SecurityAlert.id.desc()).all()
    return jsonify([_serialize_alert(a) for a in rows])


@bp.post("/alerts/<int:alert_id>/acknowledge")
@jwt_required()
def acknowledge_alert(alert_id: int):
    uid = int(get_jwt_identity())
    alert = db.session.get(SecurityAlert, alert_id)
    if not alert or alert.user_id != uid:
        return jsonify(error="not found"), 404
    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_serialize_alert(alert)), 200


@bp.get("/login-stats")
@jwt_required()
def login_stats():
    uid = int(get_jwt_identity())
    events = db.session.query(LoginEvent).filter(LoginEvent.user_id == uid).all()
    alerts = db.session.query(SecurityAlert).filter(SecurityAlert.user_id == uid).all()
    devices = db.session.query(TrustedDevice).filter(TrustedDevice.user_id == uid).all()
    return jsonify(
        total_events=len(events),
        successful_logins=sum(1 for e in events if e.success),
        failed_logins=sum(1 for e in events if not e.success),
        suspicious_events=sum(1 for e in events if e.is_suspicious),
        total_alerts=len(alerts),
        unacknowledged_alerts=sum(1 for a in alerts if not a.acknowledged),
        trusted_devices_count=len(devices),
    )


@bp.get("/devices")
@jwt_required()
def list_trusted_devices():
    uid = int(get_jwt_identity())
    rows = (
        db.session.query(TrustedDevice)
        .filter_by(user_id=uid)
        .order_by(TrustedDevice.id.asc())
        .all()
    )
    return jsonify(
        [
            {
                "id": d.id,
                "device_fingerprint": d.device_fingerprint,
                "label": d.label,
                "user_agent": d.user_agent,
                "last_ip": d.last_ip,
                "trusted_at": d.trusted_at.isoformat(),
            }
            for d in rows
        ]
    )


@bp.post("/devices/trust")
@jwt_required()
def trust_device():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    meta = extract_request_metadata(request)
    fp = data.get("device_fingerprint") or meta["device_fingerprint"]
    existing = (
        db.session.query(TrustedDevice)
        .filter_by(user_id=uid, device_fingerprint=fp)
        .first()
    )
    if existing:
        existing.last_seen_at = datetime.utcnow()
        existing.last_ip = meta["ip_address"]
        db.session.commit()
        return jsonify(id=existing.id, device_fingerprint=existing.device_fingerprint), 200

    td = TrustedDevice(
        user_id=uid,
        device_fingerprint=fp,
        label=data.get("label") or "Trusted Device",
        user_agent=meta["user_agent"],
        last_ip=meta["ip_address"],
    )
    db.session.add(td)
    db.session.commit()
    return jsonify(id=td.id, device_fingerprint=td.device_fingerprint), 201
