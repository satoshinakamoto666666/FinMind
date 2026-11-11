from datetime import datetime, timedelta
import hashlib
import json

from flask import Request
from ..extensions import db
from ..models import AuditLog, LoginEvent, SecurityAlert, TrustedDevice, User


def compute_device_fingerprint(user_agent: str, explicit_fp: str | None = None) -> str:
    if explicit_fp and explicit_fp.strip():
        return explicit_fp.strip()[:128]
    normalized = (user_agent or "unknown-agent").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def extract_request_metadata(req: Request) -> dict:
    forwarded = req.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = req.remote_addr or "127.0.0.1"
    ua = (req.headers.get("User-Agent") or "unknown").strip()[:500]
    explicit_fp = req.headers.get("X-Device-Fingerprint")
    country = (
        req.headers.get("X-Country-Code")
        or req.headers.get("CF-IPCountry")
        or ""
    ).strip().upper() or None
    return {
        "ip_address": ip,
        "user_agent": ua,
        "device_fingerprint": compute_device_fingerprint(ua, explicit_fp),
        "country_code": country,
    }


def evaluate_and_record_login(
    *,
    user: User | None,
    email: str,
    success: bool,
    ip_address: str,
    user_agent: str,
    device_fingerprint: str,
    country_code: str | None = None,
    now: datetime | None = None,
) -> dict:
    current_time = now or datetime.utcnow()
    reasons: list[str] = []
    score = 0.0

    uid = user.id if user else None

    # 1. Check recent failed login burst (brute force detection) in last 15 minutes
    window_start = current_time - timedelta(minutes=15)
    recent_failures_q = db.session.query(LoginEvent).filter(
        LoginEvent.success.is_(False),
        LoginEvent.created_at >= window_start,
        (LoginEvent.email == email) | (LoginEvent.ip_address == ip_address),
    )
    recent_failures = recent_failures_q.count()
    # Include the current attempt if it is a failure
    effective_failures = recent_failures + (0 if success else 1)
    if effective_failures >= 3:
        score += 0.55
        reasons.append("BRUTE_FORCE_BURST")

    if uid is not None:
        prior_successes = (
            db.session.query(LoginEvent)
            .filter(LoginEvent.user_id == uid, LoginEvent.success.is_(True))
            .order_by(LoginEvent.created_at.desc(), LoginEvent.id.desc())
            .all()
        )
        trusted_fps = {
            td.device_fingerprint
            for td in db.session.query(TrustedDevice).filter_by(user_id=uid).all()
        }

        if prior_successes:
            known_ips = {e.ip_address for e in prior_successes}
            known_fps = {e.device_fingerprint for e in prior_successes} | trusted_fps

            # 2. New IP address detection
            if ip_address not in known_ips:
                score += 0.30
                reasons.append("NEW_IP_ADDRESS")

            # 3. New device / user-agent detection
            if device_fingerprint not in known_fps:
                score += 0.25
                reasons.append("NEW_DEVICE_FINGERPRINT")

            # 4. Impossible travel / geo-velocity anomaly (different country within 2 hours)
            last_login = prior_successes[0]
            if (
                country_code
                and last_login.country_code
                and country_code != last_login.country_code
                and (current_time - last_login.created_at) <= timedelta(hours=2)
            ):
                score += 0.45
                reasons.append("IMPOSSIBLE_TRAVEL_GEO")
        else:
            # First successful login: auto-register trusted device baseline
            if success and device_fingerprint not in trusted_fps:
                db.session.add(
                    TrustedDevice(
                        user_id=uid,
                        device_fingerprint=device_fingerprint,
                        label="Primary Device",
                        user_agent=user_agent,
                        last_ip=ip_address,
                        trusted_at=current_time,
                        last_seen_at=current_time,
                    )
                )

    risk_score = round(min(score, 1.0), 2)
    is_suspicious = risk_score >= 0.30

    event = LoginEvent(
        user_id=uid,
        email=email or "unknown",
        ip_address=ip_address,
        user_agent=user_agent,
        device_fingerprint=device_fingerprint,
        country_code=country_code,
        success=success,
        risk_score=risk_score,
        is_suspicious=is_suspicious,
        reasons_json=json.dumps(reasons),
        created_at=current_time,
    )
    db.session.add(event)
    db.session.flush()

    alert_dict = None
    if is_suspicious and uid is not None:
        if risk_score >= 0.70 or "IMPOSSIBLE_TRAVEL_GEO" in reasons:
            severity = "CRITICAL"
        elif risk_score >= 0.50 or "BRUTE_FORCE_BURST" in reasons:
            severity = "HIGH"
        else:
            severity = "MEDIUM"

        primary_type = reasons[0] if reasons else "SUSPICIOUS_LOGIN"
        msg = (
            f"Suspicious login {'attempt' if not success else 'activity'} detected "
            f"from IP {ip_address} ({', '.join(reasons)})."
        )
        alert = SecurityAlert(
            user_id=uid,
            login_event_id=event.id,
            severity=severity,
            alert_type=primary_type,
            reason_codes_json=json.dumps(reasons),
            message=msg,
            acknowledged=False,
            created_at=current_time,
        )
        db.session.add(alert)
        db.session.add(
            AuditLog(
                user_id=uid,
                action=f"SECURITY_ALERT:{primary_type}:{severity}",
                created_at=current_time,
            )
        )
        db.session.flush()
        alert_dict = {
            "id": alert.id,
            "severity": alert.severity,
            "alert_type": alert.alert_type,
            "reasons": reasons,
            "message": alert.message,
        }

    db.session.commit()
    return {
        "login_event_id": event.id,
        "risk_score": risk_score,
        "is_suspicious": is_suspicious,
        "reasons": reasons,
        "alert": alert_dict,
    }
