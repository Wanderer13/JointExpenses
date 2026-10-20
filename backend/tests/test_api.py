from __future__ import annotations


def _register(client, name: str, email: str, password: str = "password123"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_login_me(client):
    created = _register(client, "Alice", "alice@example.com")
    assert created["user"]["email"] == "alice@example.com"
    login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers=_auth_header(login.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["name"] == "Alice"


def test_duplicate_register_rejected(client):
    _register(client, "Alice", "dup@example.com")
    res = client.post(
        "/api/auth/register",
        json={"name": "Alice2", "email": "dup@example.com", "password": "password123"},
    )
    assert res.status_code == 400


def test_group_invite_join_and_expense_flow(client):
    alice = _register(client, "Alice", "a@example.com")
    bob = _register(client, "Bob", "b@example.com")
    cara = _register(client, "Cara", "c@example.com")

    ah = _auth_header(alice["access_token"])
    bh = _auth_header(bob["access_token"])
    ch = _auth_header(cara["access_token"])

    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "Cabin", "currency": "EUR", "reminder_days": 5},
    ).json()
    token = group["invite_token"]
    gid = group["id"]

    assert client.post(f"/api/groups/join/{token}", headers=bh).status_code == 200
    assert client.post(f"/api/groups/join/{token}", headers=ch).status_code == 200

    members = client.get(f"/api/groups/{gid}", headers=ah).json()["members"]
    member_ids = [m["user_id"] for m in members]
    assert len(member_ids) == 3

    expense = client.post(
        f"/api/groups/{gid}/expenses",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 1001,
            "split_type": "equal",
            "participants": [{"user_id": uid} for uid in member_ids],
            "category": "food",
            "expense_date": "2026-10-01",
            "comment": "groceries",
        },
    )
    assert expense.status_code == 200, expense.text
    splits = expense.json()["splits"]
    assert sum(s["amount_cents"] for s in splits) == 1001

    balances = client.get(f"/api/groups/{gid}/balances", headers=ah).json()
    assert balances["sum_check"] == 0
    assert balances["suggested_transfers"]

    transfer = balances["suggested_transfers"][0]
    settlement = client.post(
        f"/api/groups/{gid}/settlements",
        headers=bh if bob["user"]["id"] == transfer["from_user_id"] else ch,
        json={
            "from_user_id": transfer["from_user_id"],
            "to_user_id": transfer["to_user_id"],
            "amount_cents": transfer["amount_cents"],
        },
    )
    # If neither bob nor cara is debtor, use the debtor's token
    if settlement.status_code != 200:
        debtor_id = transfer["from_user_id"]
        token_map = {
            alice["user"]["id"]: alice["access_token"],
            bob["user"]["id"]: bob["access_token"],
            cara["user"]["id"]: cara["access_token"],
        }
        settlement = client.post(
            f"/api/groups/{gid}/settlements",
            headers=_auth_header(token_map[debtor_id]),
            json={
                "from_user_id": transfer["from_user_id"],
                "to_user_id": transfer["to_user_id"],
                "amount_cents": transfer["amount_cents"],
            },
        )
    assert settlement.status_code == 200, settlement.text
    sid = settlement.json()["id"]
    assert settlement.json()["status"] == "pending"

    # Balances unchanged while pending
    mid = client.get(f"/api/groups/{gid}/balances", headers=ah).json()
    assert mid["suggested_transfers"][0]["amount_cents"] == transfer["amount_cents"]

    recipient_id = transfer["to_user_id"]
    token_map = {
        alice["user"]["id"]: alice["access_token"],
        bob["user"]["id"]: bob["access_token"],
        cara["user"]["id"]: cara["access_token"],
    }
    conf = client.post(
        f"/api/settlements/{sid}/action",
        headers=_auth_header(token_map[recipient_id]),
        json={"action": "confirm"},
    )
    assert conf.status_code == 200
    assert conf.json()["status"] == "confirmed"

    after = client.get(f"/api/groups/{gid}/balances", headers=ah).json()
    assert after["sum_check"] == 0
    assert len(after["suggested_transfers"]) < len(balances["suggested_transfers"]) or after[
        "suggested_transfers"
    ] == []


def test_closed_group_blocks_expenses(client):
    alice = _register(client, "Owner", "owner@example.com")
    ah = _auth_header(alice["access_token"])
    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "ClosedSoon", "currency": "USD", "reminder_days": 7},
    ).json()
    gid = group["id"]
    assert client.post(f"/api/groups/{gid}/close", headers=ah).status_code == 200

    blocked = client.post(
        f"/api/groups/{gid}/expenses",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 100,
            "split_type": "equal",
            "participants": [{"user_id": alice["user"]["id"]}],
            "category": "x",
            "expense_date": "2026-10-01",
        },
    )
    assert blocked.status_code == 400
    assert "closed" in blocked.json()["detail"].lower()

    assert client.post(f"/api/groups/{gid}/reopen", headers=ah).status_code == 200
    ok = client.post(
        f"/api/groups/{gid}/expenses",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 100,
            "split_type": "equal",
            "participants": [{"user_id": alice["user"]["id"]}],
            "category": "x",
            "expense_date": "2026-10-01",
        },
    )
    assert ok.status_code == 200


def test_settlement_only_recipient_can_confirm(client):
    alice = _register(client, "Alice", "s1@example.com")
    bob = _register(client, "Bob", "s2@example.com")
    ah = _auth_header(alice["access_token"])
    bh = _auth_header(bob["access_token"])

    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "Pair", "currency": "USD", "reminder_days": 7},
    ).json()
    token = group["invite_token"]
    client.post(f"/api/groups/join/{token}", headers=bh)
    gid = group["id"]

    client.post(
        f"/api/groups/{gid}/expenses",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 200,
            "split_type": "equal",
            "participants": [
                {"user_id": alice["user"]["id"]},
                {"user_id": bob["user"]["id"]},
            ],
            "category": "taxi",
            "expense_date": "2026-10-01",
        },
    )
    settlement = client.post(
        f"/api/groups/{gid}/settlements",
        headers=bh,
        json={
            "from_user_id": bob["user"]["id"],
            "to_user_id": alice["user"]["id"],
            "amount_cents": 100,
        },
    ).json()

    forbidden = client.post(
        f"/api/settlements/{settlement['id']}/action",
        headers=bh,
        json={"action": "confirm"},
    )
    assert forbidden.status_code == 403

    ok = client.post(
        f"/api/settlements/{settlement['id']}/action",
        headers=ah,
        json={"action": "confirm"},
    )
    assert ok.status_code == 200
