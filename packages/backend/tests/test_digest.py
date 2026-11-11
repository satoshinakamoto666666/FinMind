from datetime import date, timedelta


def test_weekly_digest_requires_auth(client):
    r = client.get("/digest/weekly")
    assert r.status_code == 401


def test_weekly_digest_empty_week_returns_valid_structure(client, auth_header):
    r = client.get("/digest/weekly?week=2026-W10", headers=auth_header)
    assert r.status_code == 200
    data = r.get_json()
    assert data["week"] == "2026-W10"
    assert data["week_start"] == "2026-03-02"
    assert data["week_end"] == "2026-03-08"
    assert data["previous_week"] == "2026-W09"
    assert data["total_spent"] == 0.0
    assert data["total_income"] == 0.0
    assert data["net_flow"] == 0.0
    assert data["previous_week_spent"] == 0.0
    assert data["week_over_week_change"] == 0.0
    assert data["week_over_week_change_pct"] == 0.0
    assert len(data["daily_breakdown"]) == 7
    assert data["category_breakdown"] == []
    assert len(data["insights"]) >= 1
    assert data["trends"]["overall_direction"] == "FLAT"


def test_weekly_digest_invalid_week_format(client, auth_header):
    for bad in ("2026-10", "2026-W00", "2026-W55", "not-a-week"):
        r = client.get(f"/digest/weekly?week={bad}", headers=auth_header)
        assert r.status_code == 400


def test_weekly_digest_aggregates_categories_and_wow_trends(client, auth_header):
    # Create two categories
    c1 = client.post("/categories", json={"name": "Dining"}, headers=auth_header).get_json()["id"]
    c2 = client.post("/categories", json={"name": "Transport"}, headers=auth_header).get_json()["id"]

    # Previous week (2026-W09: 2026-02-23 to 2026-03-01)
    client.post(
        "/expenses",
        json={"amount": 200, "description": "Last week dinner", "date": "2026-02-24", "category_id": c1},
        headers=auth_header,
    )
    client.post(
        "/expenses",
        json={"amount": 100, "description": "Last week metro", "date": "2026-02-25", "category_id": c2},
        headers=auth_header,
    )

    # Current week (2026-W10: 2026-03-02 to 2026-03-08)
    client.post(
        "/expenses",
        json={"amount": 300, "description": "This week dinner", "date": "2026-03-03", "category_id": c1},
        headers=auth_header,
    )
    client.post(
        "/expenses",
        json={"amount": 50, "description": "This week cab", "date": "2026-03-05", "category_id": c2},
        headers=auth_header,
    )
    client.post(
        "/expenses",
        json={"amount": 1000, "description": "Weekly freelance payout", "date": "2026-03-06", "expense_type": "INCOME"},
        headers=auth_header,
    )

    r = client.get("/digest/weekly?week=2026-W10", headers=auth_header)
    assert r.status_code == 200
    data = r.get_json()
    assert data["total_spent"] == 350.0
    assert data["total_income"] == 1000.0
    assert data["net_flow"] == 650.0
    assert data["previous_week_spent"] == 300.0
    assert data["week_over_week_change"] == 50.0
    assert data["week_over_week_change_pct"] == 16.67
    assert data["trends"]["overall_direction"] == "UP"
    assert data["trends"]["top_category"]["category_name"] == "Dining"
    assert data["trends"]["biggest_increase"]["category_name"] == "Dining"
    assert data["trends"]["biggest_decrease"]["category_name"] == "Transport"

    by_name = {c["category_name"]: c for c in data["category_breakdown"]}
    assert by_name["Dining"]["trend"] == "UP"
    assert by_name["Dining"]["change_pct"] == 50.0
    assert by_name["Transport"]["trend"] == "DOWN"
    assert by_name["Transport"]["change_pct"] == -50.0


def test_weekly_digest_currency_isolation(client, auth_header):
    client.post(
        "/expenses",
        json={"amount": 500, "currency": "INR", "description": "INR item", "date": "2026-03-03"},
        headers=auth_header,
    )
    client.post(
        "/expenses",
        json={"amount": 80, "currency": "USD", "description": "USD item", "date": "2026-03-04"},
        headers=auth_header,
    )

    r_inr = client.get("/digest/weekly?week=2026-W10&currency=INR", headers=auth_header).get_json()
    r_usd = client.get("/digest/weekly?week=2026-W10&currency=USD", headers=auth_header).get_json()
    assert r_inr["total_spent"] == 500.0
    assert r_inr["currency"] == "INR"
    assert r_usd["total_spent"] == 80.0
    assert r_usd["currency"] == "USD"


def test_weekly_digest_includes_upcoming_bills(client, auth_header):
    today = date.today()
    iso_y, iso_w, _ = today.isocalendar()
    week_str = f"{iso_y:04d}-W{iso_w:02d}"
    due = (today + timedelta(days=2)).isoformat()

    r_bill = client.post(
        "/bills",
        json={"name": "Broadband Fiber", "amount": 999, "next_due_date": due, "cadence": "MONTHLY"},
        headers=auth_header,
    )
    assert r_bill.status_code == 201

    r = client.get(f"/digest/weekly?week={week_str}", headers=auth_header)
    assert r.status_code == 200
    data = r.get_json()
    assert any(b["name"] == "Broadband Fiber" for b in data["upcoming_bills"])


def test_weekly_digest_cache_invalidation_on_new_expense(client, auth_header):
    r1 = client.get("/digest/weekly?week=2026-W10", headers=auth_header).get_json()
    assert r1["total_spent"] == 0.0

    client.post(
        "/expenses",
        json={"amount": 125.5, "description": "Coffee Beans", "date": "2026-03-04"},
        headers=auth_header,
    )
    r2 = client.get("/digest/weekly?week=2026-W10", headers=auth_header).get_json()
    assert r2["total_spent"] == 125.5


def test_weekly_digest_gemini_enrichment_and_fallback(client, auth_header, monkeypatch):
    def _mock_gemini(summary_context, api_key, model, persona):
        return ["AI tip 1: Great savings velocity", "AI tip 2: Dining is within range"]

    monkeypatch.setattr("app.services.digest._gemini_weekly_insights", _mock_gemini)
    r = client.get(
        "/digest/weekly?week=2026-W10",
        headers={**auth_header, "X-Gemini-Api-Key": "test-key"},
    )
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["method"] == "gemini"
    assert payload["insights"] == ["AI tip 1: Great savings velocity", "AI tip 2: Dining is within range"]

    def _fail_gemini(*_args, **_kwargs):
        raise RuntimeError("Gemini quota error")

    monkeypatch.setattr("app.services.digest._gemini_weekly_insights", _fail_gemini)
    r_fb = client.get(
        "/digest/weekly?week=2026-W10",
        headers={**auth_header, "X-Gemini-Api-Key": "test-key"},
    )
    assert r_fb.status_code == 200
    fb_data = r_fb.get_json()
    assert fb_data["method"] == "heuristic"
    assert "gemini_unavailable" in fb_data["warnings"]


def test_weekly_digest_send_notification_and_insights_alias(client, auth_header):
    r_send = client.post(
        "/digest/weekly/send",
        json={"week": "2026-W10", "channel": "email"},
        headers=auth_header,
    )
    assert r_send.status_code == 201
    sent = r_send.get_json()
    assert sent["status"] == "sent"
    assert sent["week"] == "2026-W10"

    r_bad = client.post(
        "/digest/weekly/send",
        json={"week": "2026-W10", "channel": "sms"},
        headers=auth_header,
    )
    assert r_bad.status_code == 400

    r_alias = client.get("/insights/weekly-digest?week=2026-W10", headers=auth_header)
    assert r_alias.status_code == 200
    assert r_alias.get_json()["week"] == "2026-W10"
