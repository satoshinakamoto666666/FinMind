import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
import secrets
import zipfile
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import (
    AdImpression,
    AuditLog,
    Bill,
    Category,
    DeletionRequest,
    Expense,
    GdprAuditLog,
    RecurringExpense,
    Reminder,
    User,
    UserSubscription,
)
from .cache import cache_delete_patterns


def compute_subject_hash(email: str) -> str:
    normalized = (email or "").strip().lower()
    return hashlib.sha256(f"finmind-gdpr:{normalized}".encode("utf-8")).hexdigest()


def record_gdpr_audit(
    subject_hash: str,
    action: str,
    user_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict | str | None = None,
) -> GdprAuditLog:
    if isinstance(details, dict):
        details_str = json.dumps(details, sort_keys=True)[:1000]
    else:
        details_str = str(details)[:1000] if details else None

    entry = GdprAuditLog(
        user_id=user_id,
        subject_hash=subject_hash,
        action=action,
        ip_address=(ip_address or "")[:64] or None,
        user_agent=(user_agent or "")[:255] or None,
        details=details_str,
        created_at=datetime.utcnow(),
    )
    db.session.add(entry)
    if user_id is not None:
        db.session.add(
            AuditLog(
                user_id=user_id,
                action=f"GDPR:{action}",
                created_at=datetime.utcnow(),
            )
        )
    db.session.commit()
    return entry


def _collect_user_pii_payload(user: User) -> dict:
    uid = user.id
    categories = (
        db.session.query(Category)
        .filter_by(user_id=uid)
        .order_by(Category.id.asc())
        .all()
    )
    expenses = (
        db.session.query(Expense)
        .filter_by(user_id=uid)
        .order_by(Expense.spent_at.desc(), Expense.id.desc())
        .all()
    )
    recurring = (
        db.session.query(RecurringExpense)
        .filter_by(user_id=uid)
        .order_by(RecurringExpense.id.asc())
        .all()
    )
    bills = (
        db.session.query(Bill)
        .filter_by(user_id=uid)
        .order_by(Bill.id.asc())
        .all()
    )
    reminders = (
        db.session.query(Reminder)
        .filter_by(user_id=uid)
        .order_by(Reminder.id.asc())
        .all()
    )
    subscriptions = (
        db.session.query(UserSubscription)
        .filter_by(user_id=uid)
        .order_by(UserSubscription.id.asc())
        .all()
    )
    ad_impressions = (
        db.session.query(AdImpression)
        .filter_by(user_id=uid)
        .order_by(AdImpression.id.asc())
        .all()
    )
    audit_logs = (
        db.session.query(AuditLog)
        .filter_by(user_id=uid)
        .order_by(AuditLog.id.asc())
        .all()
    )

    data = {
        "profile": {
            "id": user.id,
            "email": user.email,
            "preferred_currency": user.preferred_currency,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in categories
        ],
        "expenses": [
            {
                "id": e.id,
                "category_id": e.category_id,
                "amount": float(e.amount),
                "currency": e.currency,
                "expense_type": e.expense_type,
                "notes": e.notes or "",
                "spent_at": e.spent_at.isoformat() if e.spent_at else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in expenses
        ],
        "recurring_expenses": [
            {
                "id": r.id,
                "category_id": r.category_id,
                "amount": float(r.amount),
                "currency": r.currency,
                "expense_type": r.expense_type,
                "notes": r.notes,
                "cadence": r.cadence.value if hasattr(r.cadence, "value") else str(r.cadence),
                "start_date": r.start_date.isoformat() if r.start_date else None,
                "end_date": r.end_date.isoformat() if r.end_date else None,
                "active": r.active,
            }
            for r in recurring
        ],
        "bills": [
            {
                "id": b.id,
                "name": b.name,
                "amount": float(b.amount),
                "currency": b.currency,
                "next_due_date": b.next_due_date.isoformat() if b.next_due_date else None,
                "cadence": b.cadence.value if hasattr(b.cadence, "value") else str(b.cadence),
                "autopay_enabled": b.autopay_enabled,
                "channel_email": b.channel_email,
                "channel_whatsapp": b.channel_whatsapp,
                "active": b.active,
            }
            for b in bills
        ],
        "reminders": [
            {
                "id": rem.id,
                "bill_id": rem.bill_id,
                "message": rem.message,
                "send_at": rem.send_at.isoformat() if rem.send_at else None,
                "sent": rem.sent,
                "channel": rem.channel,
            }
            for rem in reminders
        ],
        "subscriptions": [
            {
                "id": s.id,
                "plan_id": s.plan_id,
                "active": s.active,
                "started_at": s.started_at.isoformat() if s.started_at else None,
            }
            for s in subscriptions
        ],
        "ad_impressions": [
            {
                "id": a.id,
                "placement": a.placement,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in ad_impressions
        ],
        "audit_logs": [
            {
                "id": log.id,
                "action": log.action,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in audit_logs
        ],
    }

    canonical_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
    checksum = hashlib.sha256(canonical_bytes).hexdigest()
    record_counts = {
        k: (1 if k == "profile" else len(v)) for k, v in data.items()
    }

    return {
        "schema_version": "1.0.0",
        "gdpr_article": "Article 15 & Article 20 (Right of Access & Data Portability)",
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "subject_hash": compute_subject_hash(user.email),
        "sha256_checksum": checksum,
        "record_counts": record_counts,
        "data": data,
    }


def generate_pii_export_dict(
    uid: int, ip_address: str | None = None, user_agent: str | None = None
) -> dict:
    user = db.session.get(User, uid)
    if not user:
        raise LookupError("User not found")
    payload = _collect_user_pii_payload(user)
    record_gdpr_audit(
        subject_hash=payload["subject_hash"],
        action="PII_EXPORT_JSON",
        user_id=uid,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"checksum": payload["sha256_checksum"], "counts": payload["record_counts"]},
    )
    return payload


def _rows_to_csv_bytes(rows: list[dict], fieldnames: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def generate_pii_export_zip(
    uid: int, ip_address: str | None = None, user_agent: str | None = None
) -> bytes:
    user = db.session.get(User, uid)
    if not user:
        raise LookupError("User not found")
    payload = _collect_user_pii_payload(user)

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pii_export.json", json.dumps(payload, indent=2).encode("utf-8"))
        zf.writestr(
            "profile.csv",
            _rows_to_csv_bytes(
                [payload["data"]["profile"]],
                ["id", "email", "preferred_currency", "role", "created_at"],
            ),
        )
        zf.writestr(
            "categories.csv",
            _rows_to_csv_bytes(
                payload["data"]["categories"], ["id", "name", "created_at"]
            ),
        )
        zf.writestr(
            "expenses.csv",
            _rows_to_csv_bytes(
                payload["data"]["expenses"],
                [
                    "id",
                    "category_id",
                    "amount",
                    "currency",
                    "expense_type",
                    "notes",
                    "spent_at",
                    "created_at",
                ],
            ),
        )
        zf.writestr(
            "bills.csv",
            _rows_to_csv_bytes(
                payload["data"]["bills"],
                [
                    "id",
                    "name",
                    "amount",
                    "currency",
                    "next_due_date",
                    "cadence",
                    "autopay_enabled",
                    "active",
                ],
            ),
        )
        zf.writestr(
            "reminders.csv",
            _rows_to_csv_bytes(
                payload["data"]["reminders"],
                ["id", "bill_id", "message", "send_at", "sent", "channel"],
            ),
        )

    record_gdpr_audit(
        subject_hash=payload["subject_hash"],
        action="PII_EXPORT_ZIP",
        user_id=uid,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"checksum": payload["sha256_checksum"], "format": "zip"},
    )
    return mem_zip.getvalue()


def request_account_deletion(
    uid: int,
    password: str,
    grace_days: int = 30,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    user = db.session.get(User, uid)
    if not user:
        raise LookupError("User not found")
    if not password or not check_password_hash(user.password_hash, password):
        raise PermissionError("Invalid password")

    grace_days = max(1, min(90, int(grace_days)))
    existing = (
        db.session.query(DeletionRequest)
        .filter_by(user_id=uid, status="PENDING")
        .first()
    )
    now = datetime.utcnow()
    scheduled_for = now + timedelta(days=grace_days)
    token = secrets.token_urlsafe(24)

    if existing:
        existing.confirmation_token = token
        existing.scheduled_for = scheduled_for
        existing.reason = (reason or "")[:500] or None
        req_obj = existing
    else:
        req_obj = DeletionRequest(
            user_id=uid,
            status="PENDING",
            confirmation_token=token,
            reason=(reason or "")[:500] or None,
            requested_at=now,
            scheduled_for=scheduled_for,
        )
        db.session.add(req_obj)
    db.session.commit()

    subject_hash = compute_subject_hash(user.email)
    record_gdpr_audit(
        subject_hash=subject_hash,
        action="PII_DELETION_REQUESTED",
        user_id=uid,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "request_id": req_obj.id,
            "scheduled_for": scheduled_for.isoformat(),
            "grace_days": grace_days,
        },
    )
    return {
        "request_id": req_obj.id,
        "status": req_obj.status,
        "confirmation_token": req_obj.confirmation_token,
        "requested_at": req_obj.requested_at.isoformat() + "Z",
        "scheduled_for": req_obj.scheduled_for.isoformat() + "Z",
        "grace_days": grace_days,
    }


def cancel_account_deletion(
    uid: int, ip_address: str | None = None, user_agent: str | None = None
) -> dict:
    user = db.session.get(User, uid)
    if not user:
        raise LookupError("User not found")
    req_obj = (
        db.session.query(DeletionRequest)
        .filter_by(user_id=uid, status="PENDING")
        .first()
    )
    if not req_obj:
        raise ValueError("No pending deletion request found")

    req_obj.status = "CANCELLED"
    req_obj.cancelled_at = datetime.utcnow()
    db.session.commit()

    record_gdpr_audit(
        subject_hash=compute_subject_hash(user.email),
        action="PII_DELETION_CANCELLED",
        user_id=uid,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"request_id": req_obj.id},
    )
    return {
        "request_id": req_obj.id,
        "status": req_obj.status,
        "cancelled_at": req_obj.cancelled_at.isoformat() + "Z",
    }


def anonymize_user_pii(
    uid: int,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    user = db.session.get(User, uid)
    if not user:
        raise LookupError("User not found")
    if not password or not check_password_hash(user.password_hash, password):
        raise PermissionError("Invalid password")

    orig_subject_hash = compute_subject_hash(user.email)
    anon_email = f"deleted-{orig_subject_hash[:12]}@anonymized.finmind.local"
    user.email = anon_email
    user.password_hash = generate_password_hash(secrets.token_urlsafe(32))

    exp_scrubbed = (
        db.session.query(Expense)
        .filter_by(user_id=uid)
        .update({Expense.notes: "[REDACTED]"}, synchronize_session=False)
    )
    rec_scrubbed = (
        db.session.query(RecurringExpense)
        .filter_by(user_id=uid)
        .update({RecurringExpense.notes: "[REDACTED]"}, synchronize_session=False)
    )
    bill_scrubbed = (
        db.session.query(Bill)
        .filter_by(user_id=uid)
        .update({Bill.name: "[REDACTED BILL]"}, synchronize_session=False)
    )
    rem_scrubbed = (
        db.session.query(Reminder)
        .filter_by(user_id=uid)
        .update({Reminder.message: "[REDACTED]"}, synchronize_session=False)
    )
    db.session.commit()

    record_gdpr_audit(
        subject_hash=orig_subject_hash,
        action="PII_ANONYMIZED",
        user_id=uid,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "anonymized_email": anon_email,
            "expenses_scrubbed": exp_scrubbed,
            "recurring_scrubbed": rec_scrubbed,
            "bills_scrubbed": bill_scrubbed,
            "reminders_scrubbed": rem_scrubbed,
        },
    )
    return {
        "status": "anonymized",
        "anonymized_email": anon_email,
        "subject_hash": orig_subject_hash,
        "scrubbed_records": {
            "expenses": exp_scrubbed,
            "recurring_expenses": rec_scrubbed,
            "bills": bill_scrubbed,
            "reminders": rem_scrubbed,
        },
    }


def execute_irreversible_deletion(
    uid: int,
    password: str | None = None,
    confirmation_token: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    user = db.session.get(User, uid)
    if not user:
        raise LookupError("User not found")

    pending_req = (
        db.session.query(DeletionRequest)
        .filter_by(user_id=uid, status="PENDING")
        .first()
    )

    verified = False
    if password and check_password_hash(user.password_hash, password):
        verified = True
    elif (
        confirmation_token
        and pending_req
        and secrets.compare_digest(pending_req.confirmation_token, confirmation_token)
    ):
        verified = True

    if not verified:
        raise PermissionError("Valid password or confirmation_token required for irreversible deletion")

    subject_hash = compute_subject_hash(user.email)

    # Cascade delete across all user-owned tables
    deleted_counts = {
        "reminders": db.session.query(Reminder).filter_by(user_id=uid).delete(synchronize_session=False),
        "expenses": db.session.query(Expense).filter_by(user_id=uid).delete(synchronize_session=False),
        "recurring_expenses": db.session.query(RecurringExpense).filter_by(user_id=uid).delete(synchronize_session=False),
        "bills": db.session.query(Bill).filter_by(user_id=uid).delete(synchronize_session=False),
        "categories": db.session.query(Category).filter_by(user_id=uid).delete(synchronize_session=False),
        "subscriptions": db.session.query(UserSubscription).filter_by(user_id=uid).delete(synchronize_session=False),
        "ad_impressions": db.session.query(AdImpression).filter_by(user_id=uid).delete(synchronize_session=False),
        "audit_logs": db.session.query(AuditLog).filter_by(user_id=uid).delete(synchronize_session=False),
        "deletion_requests": db.session.query(DeletionRequest).filter_by(user_id=uid).delete(synchronize_session=False),
    }
    # Detach user_id on prior GdprAuditLog rows while preserving subject_hash
    db.session.query(GdprAuditLog).filter_by(user_id=uid).update(
        {GdprAuditLog.user_id: None}, synchronize_session=False
    )
    db.session.delete(user)
    db.session.commit()

    # Purge Redis cache keys for this user
    cache_delete_patterns(
        [
            f"user:{uid}:*",
            f"insights:{uid}:*",
        ]
    )

    # Record immutable GDPR erasure log (user_id=None so it survives deletion)
    audit_entry = record_gdpr_audit(
        subject_hash=subject_hash,
        action="PII_HARD_DELETED",
        user_id=None,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"deleted_counts": deleted_counts},
    )

    return {
        "status": "deleted",
        "irreversible": True,
        "subject_hash": subject_hash,
        "audit_log_id": audit_entry.id,
        "deleted_counts": deleted_counts,
        "deleted_at": audit_entry.created_at.isoformat() + "Z",
    }


def list_gdpr_audit_logs(uid: int | None = None, subject_hash: str | None = None) -> list[dict]:
    q = db.session.query(GdprAuditLog)
    if subject_hash:
        q = q.filter(GdprAuditLog.subject_hash == subject_hash)
    elif uid is not None:
        user = db.session.get(User, uid)
        if user:
            sh = compute_subject_hash(user.email)
            q = q.filter(
                (GdprAuditLog.user_id == uid) | (GdprAuditLog.subject_hash == sh)
            )
        else:
            q = q.filter(GdprAuditLog.user_id == uid)

    rows = q.order_by(GdprAuditLog.created_at.desc(), GdprAuditLog.id.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "subject_hash": r.subject_hash,
            "action": r.action,
            "ip_address": r.ip_address,
            "user_agent": r.user_agent,
            "details": json.loads(r.details) if r.details and r.details.startswith("{") else r.details,
            "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
        }
        for r in rows
    ]
