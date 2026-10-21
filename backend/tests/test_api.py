from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.config import get_settings
from app.services.google_auth import GoogleAuthError


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
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


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


def test_group_currency_allowlist(client):
    alice = _register(client, "Owner", "currency@example.com")
    ah = _auth_header(alice["access_token"])

    bad = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "BadCur", "currency": "FOO", "reminder_days": 7},
    )
    assert bad.status_code == 422

    ok = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "EuroTrip", "currency": "eur", "reminder_days": 7},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["currency"] == "EUR"

    gid = ok.json()["id"]
    patched = client.patch(
        f"/api/groups/{gid}",
        headers=ah,
        json={"currency": "GBP"},
    )
    assert patched.status_code == 200
    assert patched.json()["currency"] == "GBP"

    rejected = client.patch(
        f"/api/groups/{gid}",
        headers=ah,
        json={"currency": "ZZZ"},
    )
    assert rejected.status_code == 422


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


def test_settlement_either_party_can_confirm(client):
    alice = _register(client, "Alice", "s1@example.com")
    bob = _register(client, "Bob", "s2@example.com")
    cara = _register(client, "Cara", "s3@example.com")
    ah = _auth_header(alice["access_token"])
    bh = _auth_header(bob["access_token"])
    ch = _auth_header(cara["access_token"])

    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "Pair", "currency": "USD", "reminder_days": 7},
    ).json()
    token = group["invite_token"]
    client.post(f"/api/groups/join/{token}", headers=bh)
    client.post(f"/api/groups/join/{token}", headers=ch)
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

    # Third party cannot confirm
    forbidden = client.post(
        f"/api/settlements/{settlement['id']}/action",
        headers=ch,
        json={"action": "confirm"},
    )
    assert forbidden.status_code == 403

    # Debtor (from_user) can confirm
    ok = client.post(
        f"/api/settlements/{settlement['id']}/action",
        headers=bh,
        json={"action": "confirm"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "confirmed"


def test_expense_complete_and_member_can_mutate(client):
    alice = _register(client, "Alice", "e1@example.com")
    bob = _register(client, "Bob", "e2@example.com")
    ah = _auth_header(alice["access_token"])
    bh = _auth_header(bob["access_token"])

    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "Pair", "currency": "USD", "reminder_days": 7},
    ).json()
    client.post(f"/api/groups/join/{group['invite_token']}", headers=bh)
    gid = group["id"]

    created = client.post(
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
            "category": "food",
            "expense_date": "2026-10-01",
        },
    )
    assert created.status_code == 200
    expense = created.json()
    assert expense["status"] == "open"
    eid = expense["id"]

    # Other member can complete
    done = client.patch(
        f"/api/expenses/{eid}",
        headers=bh,
        json={"status": "completed"},
    )
    assert done.status_code == 200
    assert done.json()["status"] == "completed"

    # Cannot edit amounts while completed
    blocked = client.patch(
        f"/api/expenses/{eid}",
        headers=bh,
        json={"category": "taxi"},
    )
    assert blocked.status_code == 400

    # Reopen then other member can edit
    reopen = client.patch(
        f"/api/expenses/{eid}",
        headers=bh,
        json={"status": "open"},
    )
    assert reopen.status_code == 200
    edited = client.patch(
        f"/api/expenses/{eid}",
        headers=bh,
        json={"category": "taxi"},
    )
    assert edited.status_code == 200
    assert edited.json()["category"] == "taxi"


def test_update_expense_amount_after_new_member(client):
    """Regression: replacing splits must not UNIQUE-fail on expense_id+user_id."""
    alice = _register(client, "Alice", "upd1@example.com")
    bob = _register(client, "Bob", "upd2@example.com")
    cara = _register(client, "Cara", "upd3@example.com")
    ah = _auth_header(alice["access_token"])
    bh = _auth_header(bob["access_token"])
    ch = _auth_header(cara["access_token"])

    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "Upd", "currency": "USD", "reminder_days": 7},
    ).json()
    token = group["invite_token"]
    gid = group["id"]
    assert client.post(f"/api/groups/join/{token}", headers=bh).status_code == 200

    created = client.post(
        f"/api/groups/{gid}/expenses",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 1000,
            "split_type": "equal",
            "participants": [
                {"user_id": alice["user"]["id"]},
                {"user_id": bob["user"]["id"]},
            ],
            "category": "food",
            "expense_date": "2026-10-01",
        },
    )
    assert created.status_code == 200, created.text
    eid = created.json()["id"]

    assert client.post(f"/api/groups/join/{token}", headers=ch).status_code == 200

    updated = client.patch(
        f"/api/expenses/{eid}",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 2500,
            "split_type": "equal",
            "participants": [
                {"user_id": alice["user"]["id"]},
                {"user_id": bob["user"]["id"]},
            ],
            "category": "food",
            "expense_date": "2026-10-01",
            "comment": None,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["amount_cents"] == 2500
    assert {s["user_id"] for s in body["splits"]} == {
        alice["user"]["id"],
        bob["user"]["id"],
    }
    assert sum(s["amount_cents"] for s in body["splits"]) == 2500


@pytest.fixture()
def google_client_id(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()
    yield "test-google-client-id.apps.googleusercontent.com"
    get_settings.cache_clear()


def test_google_auth_not_configured(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    get_settings.cache_clear()
    try:
        res = client.post("/api/auth/google", json={"credential": "fake-token"})
        assert res.status_code == 503
    finally:
        get_settings.cache_clear()


def test_google_auth_creates_user(client, google_client_id):
    claims = {
        "sub": "google-sub-1",
        "email": "gina@gmail.com",
        "email_verified": True,
        "name": "Gina Google",
        "iss": "https://accounts.google.com",
    }
    with patch("app.routers.auth.verify_google_id_token", return_value=claims):
        res = client.post("/api/auth/google", json={"credential": "fake-id-token"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["email"] == "gina@gmail.com"
    assert body["user"]["name"] == "Gina Google"
    assert body["access_token"]

    login = client.post(
        "/api/auth/login",
        json={"email": "gina@gmail.com", "password": "anything"},
    )
    assert login.status_code == 401


def test_google_auth_links_existing_email(client, google_client_id):
    created = _register(client, "Alice", "alice@link.com")
    claims = {
        "sub": "google-sub-link",
        "email": "alice@link.com",
        "email_verified": True,
        "name": "Alice G",
        "iss": "https://accounts.google.com",
    }
    with patch("app.routers.auth.verify_google_id_token", return_value=claims):
        blocked = client.post("/api/auth/google", json={"credential": "fake-id-token"})
        assert blocked.status_code == 409
        res = client.post(
            "/api/auth/google",
            json={"credential": "fake-id-token", "password": "password123"},
        )
    assert res.status_code == 200
    assert res.json()["user"]["id"] == created["user"]["id"]

    login = client.post(
        "/api/auth/login",
        json={"email": "alice@link.com", "password": "password123"},
    )
    assert login.status_code == 200


def test_google_auth_rejects_bad_token(client, google_client_id):
    with patch(
        "app.routers.auth.verify_google_id_token",
        side_effect=GoogleAuthError("Invalid Google credential"),
    ):
        res = client.post("/api/auth/google", json={"credential": "bad"})
    assert res.status_code == 401


def test_google_auth_rejects_unverified_email(client, google_client_id):
    with patch(
        "app.routers.auth.verify_google_id_token",
        side_effect=GoogleAuthError("Google email is not verified"),
    ):
        res = client.post("/api/auth/google", json={"credential": "unverified"})
    assert res.status_code == 401


def test_invite_email_returns_join_url_and_auto_join_on_register(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MAIL_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("FRONTEND_URL", "http://127.0.0.1:5173")
    get_settings.cache_clear()
    try:
        alice = _register(client, "Alice", "alice-inv@example.com")
        ah = _auth_header(alice["access_token"])
        group = client.post(
            "/api/groups",
            headers=ah,
            json={"name": "Trip", "currency": "USD", "reminder_days": 7},
        ).json()
        gid = group["id"]
        token = group["invite_token"]

        invite = client.post(
            f"/api/groups/{gid}/invite-email",
            headers=ah,
            json={"email": "newbie@example.com"},
        )
        assert invite.status_code == 200, invite.text
        body = invite.json()
        assert body["join_url"] == f"http://127.0.0.1:5173/join/{token}"
        assert body["message"]

        outbox_files = list(tmp_path.glob("*.json"))
        assert len(outbox_files) == 1
        mail = json.loads(outbox_files[0].read_text(encoding="utf-8"))
        assert body["join_url"] in mail["body"]
        assert body["join_url"] in mail["body_html"]
        assert mail["meta"]["join_url"] == body["join_url"]

        newbie = _register(client, "Newbie", "newbie@example.com")
        nh = _auth_header(newbie["access_token"])
        groups = client.get("/api/groups", headers=nh).json()
        assert len(groups) == 1
        assert groups[0]["id"] == gid
        member_ids = [m["user_id"] for m in groups[0]["members"]]
        assert newbie["user"]["id"] in member_ids
    finally:
        get_settings.cache_clear()


def test_invite_auto_join_on_login(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MAIL_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("FRONTEND_URL", "http://ui.test")
    get_settings.cache_clear()
    try:
        alice = _register(client, "Alice", "alice-login-inv@example.com")
        bob = _register(client, "Bob", "bob-login-inv@example.com")
        ah = _auth_header(alice["access_token"])
        group = client.post(
            "/api/groups",
            headers=ah,
            json={"name": "Flat", "currency": "USD", "reminder_days": 7},
        ).json()
        assert (
            client.post(
                f"/api/groups/{group['id']}/invite-email",
                headers=ah,
                json={"email": "bob-login-inv@example.com"},
            ).status_code
            == 200
        )

        login = client.post(
            "/api/auth/login",
            json={"email": "bob-login-inv@example.com", "password": "password123"},
        )
        assert login.status_code == 200
        bh = _auth_header(login.json()["access_token"])
        groups = client.get("/api/groups", headers=bh).json()
        assert any(g["id"] == group["id"] for g in groups)
    finally:
        get_settings.cache_clear()


def test_join_by_token_clears_pending_invite(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MAIL_OUTBOX_DIR", str(tmp_path))
    monkeypatch.setenv("FRONTEND_URL", "http://ui.test")
    get_settings.cache_clear()
    try:
        alice = _register(client, "Alice", "alice-tok@example.com")
        ah = _auth_header(alice["access_token"])
        group = client.post(
            "/api/groups",
            headers=ah,
            json={"name": "TokenJoin", "currency": "USD", "reminder_days": 7},
        ).json()
        # Register without pending invite first, then invite that email and join via token
        # (register would auto-join if invite existed first)
        erin = _register(client, "Erin", "erin-token@example.com")
        assert (
            client.post(
                f"/api/groups/{group['id']}/invite-email",
                headers=ah,
                json={"email": "erin-token@example.com"},
            ).status_code
            == 200
        )
        eh = _auth_header(erin["access_token"])
        # Not a member yet — invite was after register
        assert client.get("/api/groups", headers=eh).json() == []
        joined = client.post(f"/api/groups/join/{group['invite_token']}", headers=eh)
        assert joined.status_code == 200
        again = client.post(
            "/api/auth/login",
            json={"email": "erin-token@example.com", "password": "password123"},
        )
        assert again.status_code == 200
        groups = client.get("/api/groups", headers=_auth_header(again.json()["access_token"])).json()
        assert sum(1 for g in groups if g["id"] == group["id"]) == 1
    finally:
        get_settings.cache_clear()


def test_closed_group_pending_invite_not_accepted(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MAIL_OUTBOX_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        alice = _register(client, "Alice", "alice-closed@example.com")
        ah = _auth_header(alice["access_token"])
        group = client.post(
            "/api/groups",
            headers=ah,
            json={"name": "ClosedSoon", "currency": "USD", "reminder_days": 7},
        ).json()
        assert (
            client.post(
                f"/api/groups/{group['id']}/invite-email",
                headers=ah,
                json={"email": "late@example.com"},
            ).status_code
            == 200
        )
        assert client.post(f"/api/groups/{group['id']}/close", headers=ah).status_code == 200
        late = _register(client, "Late", "late@example.com")
        lh = _auth_header(late["access_token"])
        groups = client.get("/api/groups", headers=lh).json()
        assert groups == []
    finally:
        get_settings.cache_clear()


def test_google_auth_accepts_pending_invite(client, google_client_id, tmp_path, monkeypatch):
    monkeypatch.setenv("MAIL_OUTBOX_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        alice = _register(client, "Alice", "alice-g-inv@example.com")
        ah = _auth_header(alice["access_token"])
        group = client.post(
            "/api/groups",
            headers=ah,
            json={"name": "GInvite", "currency": "USD", "reminder_days": 7},
        ).json()
        assert (
            client.post(
                f"/api/groups/{group['id']}/invite-email",
                headers=ah,
                json={"email": "gina-inv@gmail.com"},
            ).status_code
            == 200
        )
        claims = {
            "sub": "google-sub-invite",
            "email": "gina-inv@gmail.com",
            "email_verified": True,
            "name": "Gina Inv",
            "iss": "https://accounts.google.com",
        }
        with patch("app.routers.auth.verify_google_id_token", return_value=claims):
            res = client.post("/api/auth/google", json={"credential": "fake-id-token"})
        assert res.status_code == 200
        gh = _auth_header(res.json()["access_token"])
        groups = client.get("/api/groups", headers=gh).json()
        assert any(g["id"] == group["id"] for g in groups)
    finally:
        get_settings.cache_clear()
