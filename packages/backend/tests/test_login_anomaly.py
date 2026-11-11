def test_baseline_login_and_new_ip_device_anomaly(client):
    email = "sec_user@finmind.io"
    password = "SecurePassword123!"
    client.post("/auth/register", json={"email": email, "password": password})

    # 1. First baseline login from home IP & Chrome
    r1 = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={
            "X-Forwarded-For": "10.10.1.1",
            "User-Agent": "Mozilla/5.0 Chrome/124.0",
            "X-Country-Code": "IN",
        },
    )
    assert r1.status_code == 200
    body1 = r1.get_json()
    assert body1["security"]["is_suspicious"] is False
    assert body1["security"]["risk_score"] == 0.0
    headers = {"Authorization": f"Bearer {body1['access_token']}"}

    # 2. Second login from a new IP, new device, and different country within 2 hours
    r2 = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={
            "X-Forwarded-For": "185.220.101.5",
            "User-Agent": "Curl/8.4.0 TorClient",
            "X-Country-Code": "RU",
        },
    )
    assert r2.status_code == 200
    body2 = r2.get_json()
    sec = body2["security"]
    assert sec["is_suspicious"] is True
    assert "NEW_IP_ADDRESS" in sec["reasons"]
    assert "NEW_DEVICE_FINGERPRINT" in sec["reasons"]
    assert "IMPOSSIBLE_TRAVEL_GEO" in sec["reasons"]
    assert sec["alert"] is not None
    assert sec["alert"]["severity"] == "CRITICAL"

    # 3. Verify /security/alerts and acknowledge alert
    alerts_res = client.get("/security/alerts?unacknowledged_only=true", headers=headers)
    assert alerts_res.status_code == 200
    alerts = alerts_res.get_json()
    assert len(alerts) == 1
    alert_id = alerts[0]["id"]

    ack_res = client.post(f"/security/alerts/{alert_id}/acknowledge", headers=headers)
    assert ack_res.status_code == 200
    assert ack_res.get_json()["acknowledged"] is True

    # Verify unacknowledged_only is now empty
    alerts_after = client.get("/security/alerts?unacknowledged_only=true", headers=headers).get_json()
    assert len(alerts_after) == 0


def test_brute_force_burst_detection_and_stats(client):
    email = "bruteforce@finmind.io"
    password = "CorrectHorseBatteryStaple!"
    client.post("/auth/register", json={"email": email, "password": password})

    # 3 rapid failed login attempts from attacker IP
    for _ in range(3):
        fail_res = client.post(
            "/auth/login",
            json={"email": email, "password": "wrong-password"},
            headers={"X-Forwarded-For": "203.0.113.55", "User-Agent": "HydraBot/1.0"},
        )
        assert fail_res.status_code == 401

    # Now log in with valid credentials to check security stats & alerts
    ok_res = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"X-Forwarded-For": "203.0.113.55", "User-Agent": "HydraBot/1.0"},
    )
    assert ok_res.status_code == 200
    token = ok_res.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    stats = client.get("/security/login-stats", headers=headers).get_json()
    assert stats["failed_logins"] == 3
    assert stats["successful_logins"] == 1
    assert stats["suspicious_events"] >= 2
    assert stats["total_alerts"] >= 1

    history = client.get("/security/login-history?suspicious_only=true", headers=headers).get_json()
    assert any("BRUTE_FORCE_BURST" in ev["reasons"] for ev in history)
