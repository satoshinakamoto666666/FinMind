from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import BackgroundJobRun, Reminder
from ..services.job_runner import (
    execute_due_reminders_job,
    get_reminder_job_stats,
    reset_dead_letter_reminder,
)

bp = Blueprint("jobs", __name__)


@bp.get("/status")
@jwt_required()
def jobs_status():
    uid = int(get_jwt_identity())
    stats = get_reminder_job_stats(user_id=uid)
    recent_runs = (
        db.session.query(BackgroundJobRun)
        .filter((BackgroundJobRun.user_id == uid) | (BackgroundJobRun.user_id.is_(None)))
        .order_by(BackgroundJobRun.id.desc())
        .limit(10)
        .all()
    )
    return jsonify(
        scheduler_status="healthy" if stats["dead_letter"] == 0 else "degraded",
        stats=stats,
        recent_runs=[
            {
                "id": run.id,
                "job_name": run.job_name,
                "status": run.status,
                "processed_count": run.processed_count,
                "succeeded_count": run.succeeded_count,
                "retried_count": run.retried_count,
                "dead_letter_count": run.dead_letter_count,
                "duration_ms": run.duration_ms,
                "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat(),
            }
            for run in recent_runs
        ],
    )


@bp.get("/reminders/stats")
@jwt_required()
def reminder_stats():
    uid = int(get_jwt_identity())
    return jsonify(get_reminder_job_stats(user_id=uid))


@bp.post("/reminders/run")
@jwt_required()
def run_reminder_jobs():
    uid = int(get_jwt_identity())
    result = execute_due_reminders_job(user_id=uid)
    return jsonify(result), 200


@bp.get("/dead-letters")
@jwt_required()
def list_dead_letters():
    uid = int(get_jwt_identity())
    items = (
        db.session.query(Reminder)
        .filter(
            Reminder.user_id == uid,
            (Reminder.failed.is_(True)) | (Reminder.retry_status == "DEAD_LETTER"),
        )
        .order_by(Reminder.id.desc())
        .all()
    )
    return jsonify(
        [
            {
                "id": r.id,
                "bill_id": r.bill_id,
                "message": r.message,
                "channel": r.channel,
                "send_at": r.send_at.isoformat(),
                "retry_count": r.retry_count,
                "max_retries": r.max_retries,
                "last_error": r.last_error,
                "last_retry_at": r.last_retry_at.isoformat() if r.last_retry_at else None,
                "retry_status": r.retry_status,
            }
            for r in items
        ]
    )


@bp.post("/dead-letters/<int:reminder_id>/reset")
@jwt_required()
def reset_dead_letter(reminder_id: int):
    uid = int(get_jwt_identity())
    r = reset_dead_letter_reminder(reminder_id, uid)
    if not r:
        return jsonify(error="not found"), 404
    return jsonify(
        id=r.id,
        retry_count=r.retry_count,
        failed=r.failed,
        retry_status=r.retry_status,
    ), 200
