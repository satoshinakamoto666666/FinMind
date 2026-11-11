import io
import json
import zipfile


def test_gdpr_export_requires_auth(client):
    r = client.get("/gdpr/export")
    assert r.status_code == 401


def test_gdpr_json_and_zip_export_contains_all_user_records(client, auth_header):
    cat = client.post("/categories", json={"name": "Healthcare"}, headers=auth_header).get_json()
    client.post(
        "/expenses",
        json={
            "amount": 450.75,
            "description": "Dental clinic visit",
            "date": "2026-03-04",
            "category_id": cat["id"],
        },
        headers=auth_header,
    )
    client.post(
        "/bills",
        json={
            "name": "Health Insurance",
            "amount": 1200.0,
            "next_due_date": "2026-03-20",
            "cadence": "MONTHLY",
        },
        headers=auth_header,
    )

    # JSON export
    r_json = client.get("/gdpr/export?format=json", headers=auth_header)
    assert r_json.status_code == 200
    payload = r_json.get_json()
    assert payload["schema_version"] == "1.0.0"
    assert len(payload["sha256_checksum"]) == 64
    assert payload["record_counts"]["profile"] == 1
    assert payload["record_counts"]["categories"] == 1
    assert payload["record_counts"]["expenses"] == 1
    assert payload["record_counts"]["bills"] == 1
    assert payload["data"]["profile"]["email"] == "test@example.com"
    assert payload["data"]["expenses"][0]["notes"] == "Dental clinic visit"

    # ZIP export
    r_zip = client.get("/gdpr/export?format=zip", headers=auth_header)
    assert r_zip.status_code == 200
    assert r_zip.mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r_zip.data)) as zf:
        names = set(zf.namelist())
        assert {
            "pii_export.json",
            "profile.csv",
            "categories.csv",
            "expenses.csv",
            "bills.csv",
            "reminders.csv",
        }.issubset(names)
        exported_json = json.loads(zf.read("pii_export.json").decode("utf-8"))
        assert len(exported_json["sha256_checksum"]) == 64
        assert exported_json["record_counts"]["audit_logs"] == payload["record_counts"]["audit_logs"] + 1

    # Invalid format returns 400
    r_bad = client.get("/gdpr/export?format=xml", headers=auth_header)
    assert r_bad.status_code == 400


def test_gdpr_deletion_request_and_cancellation_workflow(client, auth_header):
    # Wrong password rejected
    r_wrong = client.post(
        "/gdpr/delete/request",
        json={"password": "wrong-password", "grace_days": 14},
        headers=auth_header,
    )
    assert r_wrong.status_code == 401

    # Valid password schedules deletion
    r_req = client.post(
        "/gdpr/delete/request",
        json={"password": "password123", "grace_days": 14, "reason": "Switching accounts"},
        headers=auth_header,
    )
    assert r_req.status_code == 201
    req_data = r_req.get_json()
    assert req_data["status"] == "PENDING"
    assert req_data["grace_days"] == 14
    assert len(req_data["confirmation_token"]) > 16

    # Cancel scheduled deletion
    r_cancel = client.post("/gdpr/delete/cancel", headers=auth_header)
    assert r_cancel.status_code == 200
    assert r_cancel.get_json()["status"] == "CANCELLED"

    # Cancelling again when none pending returns 404
    r_cancel_again = client.post("/gdpr/delete/cancel", headers=auth_header)
    assert r_cancel_again.status_code == 404


def test_gdpr_anonymize_scrubs_pii_while_preserving_audit_trail(client, auth_header):
    client.post(
        "/expenses",
        json={"amount": 99.0, "description": "Private medical note", "date": "2026-03-04"},
        headers=auth_header,
    )
    r_anon = client.post(
        "/gdpr/anonymize",
        json={"password": "password123"},
        headers=auth_header,
    )
    assert r_anon.status_code == 200
    anon_data = r_anon.get_json()
    assert anon_data["status"] == "anonymized"
    assert anon_data["anonymized_email"].endswith("@anonymized.finmind.local")
    assert anon_data["scrubbed_records"]["expenses"] == 1

    # Verify expense note was scrubbed
    exps = client.get("/expenses", headers=auth_header).get_json()
    assert exps[0]["description"] == "[REDACTED]"


def test_gdpr_irreversible_hard_deletion_cascades_and_preserves_immutable_audit_log(
    client, auth_header
):
    # Populate data across tables
    cat = client.post("/categories", json={"name": "Personal"}, headers=auth_header).get_json()
    client.post(
        "/expenses",
        json={"amount": 250, "description": "Flight ticket", "date": "2026-03-05", "category_id": cat["id"]},
        headers=auth_header,
    )
    client.post(
        "/bills",
        json={"name": "Mobile Postpaid", "amount": 599, "next_due_date": "2026-03-15", "cadence": "MONTHLY"},
        headers=auth_header,
    )

    # First export to create an audit trail entry
    client.get("/gdpr/export?format=json", headers=auth_header)

    # Request deletion token
    req_data = client.post(
        "/gdpr/delete/request",
        json={"password": "password123"},
        headers=auth_header,
    ).get_json()
    token = req_data["confirmation_token"]

    # Confirm irreversible deletion using confirmation_token
    r_del = client.post(
        "/gdpr/delete/confirm",
        json={"confirmation_token": token},
        headers=auth_header,
    )
    assert r_del.status_code == 200
    del_data = r_del.get_json()
    assert del_data["status"] == "deleted"
    assert del_data["irreversible"] is True
    assert del_data["deleted_counts"]["expenses"] == 1
    assert del_data["deleted_counts"]["categories"] == 1
    assert del_data["deleted_counts"]["bills"] == 1
    subject_hash = del_data["subject_hash"]

    # User profile no longer exists
    r_me = client.get("/auth/me", headers=auth_header)
    assert r_me.status_code == 404

    # Login with old credentials fails
    r_login = client.post(
        "/auth/login", json={"email": "test@example.com", "password": "password123"}
    )
    assert r_login.status_code == 401

    # Register a new admin/auditor user and verify immutable GDPR audit trail survived user deletion
    client.post("/auth/register", json={"email": "auditor@example.com", "password": "password123"})
    auditor_token = client.post(
        "/auth/login", json={"email": "auditor@example.com", "password": "password123"}
    ).get_json()["access_token"]
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    r_logs = client.get(
        f"/gdpr/audit-logs?subject_hash={subject_hash}", headers=auditor_headers
    )
    assert r_logs.status_code == 200
    logs = r_logs.get_json()["audit_logs"]
    actions = [entry["action"] for entry in logs]
    assert "PII_EXPORT_JSON" in actions
    assert "PII_DELETION_REQUESTED" in actions
    assert "PII_HARD_DELETED" in actions
    assert all(entry["user_id"] is None for entry in logs)
