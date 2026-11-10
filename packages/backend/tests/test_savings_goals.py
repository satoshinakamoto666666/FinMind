from datetime import date, timedelta


def test_savings_goals_crud_and_milestone_unlocks(client, auth_header):
    # Initially empty
    r = client.get("/savings-goals", headers=auth_header)
    assert r.status_code == 200
    assert r.get_json() == []

    # Create a savings goal with auto-generated 25/50/75/100% milestones
    target_date = (date.today() + timedelta(days=90)).isoformat()
    payload = {
        "name": "Emergency Fund",
        "target_amount": 1000.00,
        "currency": "USD",
        "target_date": target_date,
        "category": "Safety Net",
        "notes": "3 months of core expenses",
    }
    r = client.post("/savings-goals", json=payload, headers=auth_header)
    assert r.status_code == 201
    goal = r.get_json()
    goal_id = goal["id"]
    assert goal["name"] == "Emergency Fund"
    assert goal["target_amount"] == 1000.0
    assert goal["current_amount"] == 0.0
    assert goal["progress_percentage"] == 0.0
    assert goal["status"] == "ACTIVE"
    assert len(goal["milestones"]) == 4
    assert [m["percentage"] for m in goal["milestones"]] == [25, 50, 75, 100]
    assert all(not m["reached"] for m in goal["milestones"])

    # Contribute $300 -> unlocks 25% ($250) milestone
    r = client.post(
        f"/savings-goals/{goal_id}/contribute",
        json={"amount": 300.00, "notes": "First deposit"},
        headers=auth_header,
    )
    assert r.status_code == 200
    updated = r.get_json()
    assert updated["current_amount"] == 300.0
    assert updated["progress_percentage"] == 30.0
    assert len(updated["newly_unlocked_milestones"]) == 1
    assert updated["newly_unlocked_milestones"][0]["percentage"] == 25
    assert updated["newly_unlocked_milestones"][0]["reached"] is True

    # Add a custom milestone at $600
    r = client.post(
        f"/savings-goals/{goal_id}/milestones",
        json={"title": "Midway Bonus", "target_amount": 600.00},
        headers=auth_header,
    )
    assert r.status_code == 201
    custom_m = r.get_json()
    assert custom_m["title"] == "Midway Bonus"
    assert custom_m["reached"] is False

    # Contribute remaining $700 -> unlocks 50%, 60%, 75%, and 100% milestones and completes goal
    r = client.post(
        f"/savings-goals/{goal_id}/contribute",
        json={"amount": 700.00, "notes": "Final deposit"},
        headers=auth_header,
    )
    assert r.status_code == 200
    completed = r.get_json()
    assert completed["current_amount"] == 1000.0
    assert completed["progress_percentage"] == 100.0
    assert completed["status"] == "COMPLETED"
    assert all(m["reached"] for m in completed["milestones"])
    assert len(completed["contributions"]) == 2

    # Update goal notes
    r = client.patch(
        f"/savings-goals/{goal_id}",
        json={"notes": "Fully funded emergency reserve"},
        headers=auth_header,
    )
    assert r.status_code == 200
    assert r.get_json()["notes"] == "Fully funded emergency reserve"

    # Delete goal
    r = client.delete(f"/savings-goals/{goal_id}", headers=auth_header)
    assert r.status_code == 200
    assert client.get("/savings-goals", headers=auth_header).get_json() == []
