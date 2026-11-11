#!/usr/bin/env python3
"""End-to-end runtime smoke verifier for FinMind deployments."""
import argparse
import json
import sys
import time
import urllib.request


def req_json(base_url: str, path: str, method: str = "GET", payload: dict | None = None, headers: dict | None = None):
    url = base_url.rstrip("/") + path
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    r = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(r, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Verify FinMind runtime deployment")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--frontend-url", default="")
    args = parser.parse_args()

    st, h = req_json(args.api_url, "/health")
    assert st == 200 and h.get("status") == "ok", f"/health failed: {st} {h}"

    st, hr = req_json(args.api_url, "/health/ready")
    assert st == 200 and hr.get("status") == "ok", f"/health/ready failed: {st} {hr}"

    email = f"smoke_{int(time.time())}@finmind.local"
    password = "SmokePassword123!"
    st, _ = req_json(args.api_url, "/auth/register", "POST", {"email": email, "password": password})
    assert st in (201, 409)
    st, tok = req_json(args.api_url, "/auth/login", "POST", {"email": email, "password": password})
    assert st == 200 and "access_token" in tok
    auth = {"Authorization": f"Bearer {tok['access_token']}"}

    st, cat = req_json(args.api_url, "/categories", "POST", {"name": "SmokeCat"}, auth)
    assert st == 201
    st, exp = req_json(args.api_url, "/expenses", "POST", {"amount": 42.5, "description": "Smoke test", "category_id": cat["id"]}, auth)
    assert st == 201
    st, bill = req_json(args.api_url, "/bills", "POST", {"name": "SmokeBill", "amount": 100, "next_due_date": "2026-12-01", "cadence": "MONTHLY"}, auth)
    assert st == 201
    st, dash = req_json(args.api_url, "/dashboard/summary", "GET", None, auth)
    assert st == 200
    st, ins = req_json(args.api_url, "/insights/budget-suggestion", "GET", None, auth)
    assert st == 200

    if args.frontend_url:
        with urllib.request.urlopen(args.frontend_url, timeout=15) as f_resp:
            assert f_resp.status == 200

    print("ALL_RUNTIME_CHECKS_PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
