from __future__ import annotations


def _register(client, name: str, email: str, password: str = "password123"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_invite_adds_member_for_expenses_before_signup(client):
    alice = _register(client, "Alice", "alice-inv@example.com")
    ah = _auth(alice["access_token"])
    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "Trip", "currency": "USD", "reminder_days": 7},
    ).json()
    gid = group["id"]

    inv = client.post(
        f"/api/groups/{gid}/invite-email",
        headers=ah,
        json={"email": "bob-inv@example.com"},
    )
    assert inv.status_code == 200, inv.text

    members = client.get(f"/api/groups/{gid}", headers=ah).json()["members"]
    emails = {m["email"]: m for m in members}
    assert "bob-inv@example.com" in emails
    assert emails["bob-inv@example.com"]["awaiting_signup"] is True
    bob_id = emails["bob-inv@example.com"]["user_id"]

    expense = client.post(
        f"/api/groups/{gid}/expenses",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 2000,
            "split_type": "equal",
            "participants": [
                {"user_id": alice["user"]["id"]},
                {"user_id": bob_id},
            ],
            "category": "food",
            "expense_date": "2026-10-01",
        },
    )
    assert expense.status_code == 200, expense.text

    claimed = _register(client, "Bob", "bob-inv@example.com")
    assert claimed["user"]["name"] == "Bob"
    assert claimed["user"]["email"] == "bob-inv@example.com"
