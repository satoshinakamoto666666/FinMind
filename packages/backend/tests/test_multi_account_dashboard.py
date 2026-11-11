from datetime import date


def _auth_headers(client, email="multiaccount@finmind.io"):
    client.post("/auth/register", json={"email": email, "password": "Password123!"})
    res = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    token = res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_list_update_archive_accounts(client):
    headers = _auth_headers(client, "crud_acc@finmind.io")

    # Create Checking & Savings accounts
    r1 = client.post(
        "/accounts",
        headers=headers,
        json={
            "name": "Primary Checking",
            "account_type": "CHECKING",
            "institution": "ICICI",
            "currency": "INR",
            "initial_balance": 25000.0,
        },
    )
    assert r1.status_code == 201
    acc1 = r1.get_json()
    assert acc1["name"] == "Primary Checking"
    assert acc1["current_balance"] == 25000.0

    r2 = client.post(
        "/accounts",
        headers=headers,
        json={
            "name": "Emergency Savings",
            "account_type": "SAVINGS",
            "currency": "INR",
            "initial_balance": 100000.0,
        },
    )
    assert r2.status_code == 201
    acc2 = r2.get_json()

    # List active accounts
    list_res = client.get("/accounts", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.get_json()) == 2

    # Update account name
    patch_res = client.patch(
        f"/accounts/{acc1['id']}",
        headers=headers,
        json={"name": "Salary Checking"},
    )
    assert patch_res.status_code == 200
    assert patch_res.get_json()["name"] == "Salary Checking"

    # Archive second account
    del_res = client.delete(f"/accounts/{acc2['id']}", headers=headers)
    assert del_res.status_code == 200
    assert len(client.get("/accounts", headers=headers).get_json()) == 1
    assert len(client.get("/accounts?include_archived=true", headers=headers).get_json()) == 2


def test_multi_account_transactions_transfers_and_dashboard(client):
    headers = _auth_headers(client, "overview_acc@finmind.io")

    checking = client.post(
        "/accounts",
        headers=headers,
        json={"name": "Main Checking", "account_type": "CHECKING", "currency": "INR", "initial_balance": 10000},
    ).get_json()
    savings = client.post(
        "/accounts",
        headers=headers,
        json={"name": "High Yield Savings", "account_type": "SAVINGS", "currency": "INR", "initial_balance": 50000},
    ).get_json()
    card = client.post(
        "/accounts",
        headers=headers,
        json={"name": "Travel Credit Card", "account_type": "CREDIT_CARD", "currency": "INR", "initial_balance": 0},
    ).get_json()

    today_str = date.today().isoformat()
    ym = date.today().strftime("%Y-%m")

    # Record income into checking (+40,000)
    client.post(
        "/expenses",
        headers=headers,
        json={
            "amount": 40000,
            "currency": "INR",
            "expense_type": "INCOME",
            "notes": "Monthly Salary",
            "spent_at": today_str,
            "account_id": checking["id"],
        },
    )

    # Record expense on checking (-5,000) and credit card (-8,000)
    client.post(
        "/expenses",
        headers=headers,
        json={
            "amount": 5000,
            "currency": "INR",
            "expense_type": "EXPENSE",
            "notes": "House Rent Split",
            "spent_at": today_str,
            "account_id": checking["id"],
        },
    )
    client.post(
        "/expenses",
        headers=headers,
        json={
            "amount": 8000,
            "currency": "INR",
            "expense_type": "EXPENSE",
            "notes": "Flight Booking",
            "spent_at": today_str,
            "account_id": card["id"],
        },
    )

    # Transfer 15,000 from Checking to Savings
    tr_res = client.post(
        "/accounts/transfers",
        headers=headers,
        json={
            "from_account_id": checking["id"],
            "to_account_id": savings["id"],
            "amount": 15000,
            "notes": "Monthly savings sweep",
        },
    )
    assert tr_res.status_code == 201

    # Verify balances:
    # Checking: 10,000 + 40,000 - 5,000 - 15,000 = 30,000
    # Savings: 50,000 + 15,000 = 65,000
    # Credit Card: 0 - 8,000 = -8,000 (liability of 8,000)
    dash_res = client.get(f"/dashboard/multi-account?month={ym}", headers=headers)
    assert dash_res.status_code == 200
    payload = dash_res.get_json()

    assert payload["consolidated"]["account_count"] == 3
    assert payload["consolidated"]["total_assets"] == 95000.0
    assert payload["consolidated"]["total_liabilities"] == 8000.0
    assert payload["consolidated"]["net_worth"] == 87000.0
    assert payload["consolidated"]["monthly_income"] == 40000.0
    assert payload["consolidated"]["monthly_expenses"] == 13000.0
    assert payload["consolidated"]["monthly_net_flow"] == 27000.0

    # Filter overview by single account
    filtered_res = client.get(
        f"/dashboard/multi-account?month={ym}&account_id={checking['id']}",
        headers=headers,
    )
    assert filtered_res.status_code == 200
    filtered = filtered_res.get_json()
    assert len(filtered["accounts"]) == 1
    assert filtered["accounts"][0]["current_balance"] == 30000.0
    assert all(tx["account_id"] == checking["id"] for tx in filtered["recent_transactions"])
