from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import time
from typing import Callable

from ..extensions import db
from ..models import BackgroundJobRun, Reminder
from ..observability import track_reminder_event
from .reminders import send_reminder

logger = logging.getLogger("finmind.jobs")


@dataclass(frozen=True)
class RetryPolicy:
    base_delay_minutes: int = 5
    backoff_factor: int = 3
    max_retries: int = 3

    def next_delay_minutes(self, attempt_number: int) -> int:
        if attempt_number <= 1:
            return self.base_delay_minutes
        return int(self.base_delay_minutes * (self.backoff_factor ** (attempt_number - 1)))

    def compute_next_retry_at(self, now: datetime, attempt_number: int) -> datetime:
        return now + timedelta(minutes=self.next_delay_minutes(attempt_number))


DEFAULT_RETRY_POLICY = RetryPolicy()


def dispatch_reminders_batch(
    candidates: list[Reminder],
    *,
    sender: Callable[[Reminder], bool] = send_reminder,
    now: datetime | None = None,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
) -> dict:
    current_time = now or datetime.utcnow()
    succeeded = 0
    retried = 0
    dead_lettered = 0

    for r in candidates:
        max_allowed = r.max_retries if (r.max_retries is not None and r.max_retries > 0) else policy.max_retries
        try:
            ok = bool(sender(r))
            error_msg = None if ok else f"Dispatch returned False for channel={r.channel}"
        except Exception as exc:
            ok = False
            error_msg = str(exc)[:500] or "Unhandled dispatch exception"

        if ok:
            r.sent = True
            r.failed = False
            r.retry_status = "SENT"
            r.last_error = None
            r.next_retry_at = None
            succeeded += 1
            track_reminder_event(event="sent", channel=r.channel, status="ok")
        else:
            r.retry_count = int(r.retry_count or 0) + 1
            r.last_retry_at = current_time
            r.last_error = error_msg
            if r.retry_count >= max_allowed:
                r.failed = True
                r.retry_status = "DEAD_LETTER"
                r.next_retry_at = None
                dead_lettered += 1
                track_reminder_event(event="dead_letter", channel=r.channel, status="failed")
            else:
                r.failed = False
                r.retry_status = "RETRYING"
                r.next_retry_at = policy.compute_next_retry_at(current_time, r.retry_count)
                retried += 1
                track_reminder_event(event="retry_scheduled", channel=r.channel, status="retrying")

    return {
        "processed": len(candidates),
        "succeeded": succeeded,
        "retried": retried,
        "dead_lettered": dead_lettered,
    }


def execute_due_reminders_job(
    *,
    user_id: int | None = None,
    now: datetime | None = None,
    sender: Callable[[Reminder], bool] = send_reminder,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
) -> dict:
    started_clock = time.perf_counter()
    started_at = datetime.utcnow()
    cutoff = (now or started_at) + timedelta(minutes=1)
    effective_now = now or started_at

    query = db.session.query(Reminder).filter(
        Reminder.sent.is_(False),
        Reminder.failed.is_(False),
        Reminder.send_at <= cutoff,
        (Reminder.next_retry_at.is_(None)) | (Reminder.next_retry_at <= effective_now),
    )
    if user_id is not None:
        query = query.filter(Reminder.user_id == user_id)

    candidates = query.order_by(Reminder.send_at.asc(), Reminder.id.asc()).all()
    batch_result = dispatch_reminders_batch(
        candidates,
        sender=sender,
        now=effective_now,
        policy=policy,
    )

    duration_ms = round((time.perf_counter() - started_clock) * 1000.0, 2)
    status = "SUCCEEDED"
    if batch_result["dead_lettered"] > 0 and batch_result["succeeded"] == 0:
        status = "FAILED"
    elif batch_result["retried"] > 0 or batch_result["dead_lettered"] > 0:
        status = "PARTIAL_FAILURE"

    job_run = BackgroundJobRun(
        job_name="reminders_dispatch",
        user_id=user_id,
        status=status,
        processed_count=batch_result["processed"],
        succeeded_count=batch_result["succeeded"],
        retried_count=batch_result["retried"],
        dead_letter_count=batch_result["dead_lettered"],
        duration_ms=duration_ms,
        started_at=started_at,
        finished_at=datetime.utcnow(),
    )
    db.session.add(job_run)
    db.session.commit()

    return {
        "job_run_id": job_run.id,
        "status": status,
        "processed": batch_result["processed"],
        "succeeded": batch_result["succeeded"],
        "retried": batch_result["retried"],
        "dead_lettered": batch_result["dead_lettered"],
        "duration_ms": duration_ms,
    }


def reset_dead_letter_reminder(reminder_id: int, user_id: int) -> Reminder | None:
    r = db.session.get(Reminder, reminder_id)
    if not r or r.user_id != user_id:
        return None
    r.retry_count = 0
    r.failed = False
    r.sent = False
    r.last_error = None
    r.next_retry_at = None
    r.retry_status = "PENDING"
    db.session.commit()
    track_reminder_event(event="dead_letter_reset", channel=r.channel, status="ok")
    return r


def get_reminder_job_stats(user_id: int | None = None) -> dict:
    q = db.session.query(Reminder)
    if user_id is not None:
        q = q.filter(Reminder.user_id == user_id)
    rows = q.all()
    total = len(rows)
    sent = sum(1 for r in rows if r.sent)
    dead_letter = sum(1 for r in rows if r.failed or r.retry_status == "DEAD_LETTER")
    retrying = sum(
        1
        for r in rows
        if not r.sent and not r.failed and (r.retry_count or 0) > 0
    )
    pending = sum(
        1
        for r in rows
        if not r.sent and not r.failed and (r.retry_count or 0) == 0
    )
    completed_attempts = sent + dead_letter
    success_rate_pct = (
        round((sent / completed_attempts) * 100.0, 2)
        if completed_attempts > 0
        else 100.0
    )
    return {
        "total": total,
        "pending": pending,
        "retrying": retrying,
        "sent": sent,
        "dead_letter": dead_letter,
        "success_rate_pct": success_rate_pct,
        "retry_policy": {
            "base_delay_minutes": DEFAULT_RETRY_POLICY.base_delay_minutes,
            "backoff_factor": DEFAULT_RETRY_POLICY.backoff_factor,
            "max_retries": DEFAULT_RETRY_POLICY.max_retries,
            "schedule_minutes": [
                DEFAULT_RETRY_POLICY.next_delay_minutes(1),
                DEFAULT_RETRY_POLICY.next_delay_minutes(2),
                DEFAULT_RETRY_POLICY.next_delay_minutes(3),
            ],
        },
    }
