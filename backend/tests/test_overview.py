from __future__ import annotations

from app.models import ExpenseStatus, SettlementStatus
from tests.helpers import add_equal_expense, add_settlement


def _register(client, name: str, email: str, password: str = "password123"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_overview_pending_balances_and_open_expenses(client, db, users, group_with_members):
    alice, bob, cara = users
    g = group_with_members
    add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=3000,
        participant_ids=[alice.id, bob.id, cara.id],
    )
    add_settlement(
        db,
        group_id=g.id,
        from_user_id=bob.id,
        to_user_id=alice.id,
        amount_cents=1000,
        status=SettlementStatus.pending,
    )

    login = client.post(
        "/api/auth/login",
        json={"email": "bob@test.com", "password": "password123"},
    )
    assert login.status_code == 200
    headers = _auth_header(login.json()["access_token"])

    overview = client.get("/api/me/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["pending_settlement_count"] == 1
    assert len(body["pending_settlements"]) == 1
    pending = body["pending_settlements"][0]
    assert pending["counterpart_email"] == "alice@test.com"
    assert pending["needs_my_action"] is True
    assert body["balances_by_currency"]
    assert body["balances_by_currency"][0]["you_owe_cents"] > 0
    assert len(body["open_expenses"]) == 1
    assert body["open_expenses"][0]["payer_email"] == "alice@test.com"


def test_balances_and_settlements_include_emails(client, db, users, group_with_members):
    alice, bob, cara = users
    g = group_with_members
    add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=3000,
        participant_ids=[alice.id, bob.id, cara.id],
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "alice@test.com", "password": "password123"},
    )
    headers = _auth_header(login.json()["access_token"])

    balances = client.get(f"/api/groups/{g.id}/balances", headers=headers).json()
    assert all(n.get("email") for n in balances["nets"])
    assert all(t.get("from_email") and t.get("to_email") for t in balances["suggested_transfers"])

    expenses = client.get(f"/api/groups/{g.id}/expenses", headers=headers).json()
    assert expenses[0]["payer_email"] == "alice@test.com"
    assert all(s.get("email") for s in expenses[0]["splits"])


def test_user_profile_shared_group_access(client, db, users, group_with_members):
    alice, bob, _cara = users
    outsider = _register(client, "Dave", "dave@example.com")
    alice_login = client.post(
        "/api/auth/login",
        json={"email": "alice@test.com", "password": "password123"},
    )
    ah = _auth_header(alice_login.json()["access_token"])
    dh = _auth_header(outsider["access_token"])

    ok = client.get(f"/api/users/{bob.id}", headers=ah)
    assert ok.status_code == 200
    body = ok.json()
    assert body["email"] == "bob@test.com"
    assert any(g["id"] == group_with_members.id for g in body["shared_groups"])

    forbidden = client.get(f"/api/users/{bob.id}", headers=dh)
    assert forbidden.status_code == 404

    self_profile = client.get(f"/api/users/{alice.id}", headers=ah)
    assert self_profile.status_code == 200
    assert self_profile.json()["email"] == "alice@test.com"


def test_completed_expense_excluded_from_open_overview(client, db, users, group_with_members):
    alice, bob, cara = users
    g = group_with_members
    expense = add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=1500,
        participant_ids=[alice.id, bob.id, cara.id],
    )
    expense.status = ExpenseStatus.completed
    db.commit()

    login = client.post(
        "/api/auth/login",
        json={"email": "alice@test.com", "password": "password123"},
    )
    headers = _auth_header(login.json()["access_token"])
    overview = client.get("/api/me/overview", headers=headers).json()
    assert overview["open_expenses"] == []
