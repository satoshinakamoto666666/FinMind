from datetime import datetime, timedelta
from app.extensions import db
from app.models import Reminder
from app.services.job_runner import (
    DEFAULT_RETRY_POLICY,
    RetryPolicy,
    dispatch_reminders_batch,
    execute_due_reminders_job,
)


def _auth_headers(client, email="jobs@finmind.io"):
    client.post("/auth/register", json={"email": email, "password": "Password123!"})
    res = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    token = res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_exponential_backoff_policy_schedule():
    policy = RetryPolicy(base_delay_minutes=5, backoff_factor=3, max_retries=3)
    assert policy.next_delay_minutes(1) == 5
    assert policy.next_delay_minutes(2) == 15
    assert policy.next_delay_minutes(3) == 45
    now = datetime(2026, 1, 1, 12, 0, 0)
    assert policy.compute_next_retry_at(now, 2) == datetime(2026, 1, 1, 12, 15, 0)


def test_dispatch_batch_transient_failure_and_recovery(app_fixture):
    with app_fixture.app_context():
        headers = _auth_headers(app_fixture.test_client(), "batch@finmind.io")
        assert headers
        r = Reminder(
            user_id=1,
            message="Pay electricity bill",
            send_at=datetime.utcnow() - timedelta(minutes=10),
            channel="email:user@finmind.io",
        )
        db.session.add(r)
        db.session.commit()

        t0 = datetime(2026, 5, 1, 10, 0, 0)
        # First attempt fails -> retry_count=1, next_retry_at = t0 + 5m, status = RETRYING
        res1 = dispatch_reminders_batch([r], sender=lambda _: False, now=t0)
        assert res1 == {"processed": 1, "succeeded": 0, "retried": 1, "dead_lettered": 0}
        assert r.retry_count == 1
        assert r.retry_status == "RETRYING"
        assert r.failed is False
        assert r.next_retry_at == t0 + timedelta(minutes=5)

        # Second attempt succeeds -> sent=True, status=SENT
        t1 = t0 + timedelta(minutes=5)
        res2 = dispatch_reminders_batch([r], sender=lambda _: True, now=t1)
        assert res2 == {"processed": 1, "succeeded": 1, "retried": 0, "dead_lettered": 0}
        assert r.sent is True
        assert r.retry_status == "SENT"
        assert r.next_retry_at is None
        assert r.last_error is None


def test_dispatch_moves_to_dead_letter_after_max_retries(app_fixture):
    with app_fixture.app_context():
        _auth_headers(app_fixture.test_client(), "dlq@finmind.io")
        r = Reminder(
            user_id=1,
            message="Broken webhook channel",
            send_at=datetime.utcnow() - timedelta(minutes=30),
            channel="whatsapp",
            max_retries=3,
        )
        db.session.add(r)
        db.session.commit()

        now = datetime(2026, 5, 1, 12, 0, 0)
        # Attempt 1 -> 5m backoff
        dispatch_reminders_batch([r], sender=lambda _: False, now=now)
        assert r.retry_count == 1
        assert r.failed is False
        assert r.next_retry_at == now + timedelta(minutes=5)

        # Attempt 2 -> 15m backoff
        now2 = r.next_retry_at
        dispatch_reminders_batch([r], sender=lambda _: False, now=now2)
        assert r.retry_count == 2
        assert r.failed is False
        assert r.next_retry_at == now2 + timedelta(minutes=15)

        # Attempt 3 -> reaches max_retries=3 -> DEAD_LETTER
        now3 = r.next_retry_at
        res3 = dispatch_reminders_batch(
            [r],
            sender=lambda _: (_ for _ in ()).throw(RuntimeError("SMTP timeout")),
            now=now3,
        )
        assert res3["dead_lettered"] == 1
        assert r.retry_count == 3
        assert r.failed is True
        assert r.retry_status == "DEAD_LETTER"
        assert r.next_retry_at is None
        assert "SMTP timeout" in (r.last_error or "")


def test_jobs_monitoring_and_dead_letter_reset_endpoints(client, app_fixture):
    headers = _auth_headers(client, "monitor@finmind.io")
    past = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

    # Create a reminder that will fail (whatsapp without number returns False in send_reminder)
    create_res = client.post(
        "/reminders",
        headers=headers,
        json={"message": "Failed WhatsApp reminder", "send_at": past, "channel": "whatsapp"},
    )
    assert create_res.status_code == 201
    rem_id = create_res.get_json()["id"]

    # Force 3 failures by advancing time in execute_due_reminders_job
    with app_fixture.app_context():
        t = datetime.utcnow()
        execute_due_reminders_job(user_id=1, now=t)
        execute_due_reminders_job(user_id=1, now=t + timedelta(minutes=6))
        execute_due_reminders_job(user_id=1, now=t + timedelta(minutes=25))

    status_res = client.get("/jobs/status", headers=headers)
    assert status_res.status_code == 200
    status_data = status_res.get_json()
    assert status_data["scheduler_status"] == "degraded"
    assert status_data["stats"]["dead_letter"] == 1
    assert len(status_data["recent_runs"]) >= 3

    dl_res = client.get("/jobs/dead-letters", headers=headers)
    assert dl_res.status_code == 200
    dl_items = dl_res.get_json()
    assert len(dl_items) == 1
    assert dl_items[0]["id"] == rem_id
    assert dl_items[0]["retry_status"] == "DEAD_LETTER"

    # Reset dead-letter item
    reset_res = client.post(f"/jobs/dead-letters/{rem_id}/reset", headers=headers)
    assert reset_res.status_code == 200
    reset_payload = reset_res.get_json()
    assert reset_payload["retry_count"] == 0
    assert reset_payload["failed"] is False
    assert reset_payload["retry_status"] == "PENDING"

    # Stats should now show 0 dead letters and healthy status
    stats_res = client.get("/jobs/reminders/stats", headers=headers)
    assert stats_res.status_code == 200
    assert stats_res.get_json()["dead_letter"] == 0
    assert stats_res.get_json()["pending"] == 1
