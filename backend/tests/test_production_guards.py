from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

from app.config import get_settings
from app.services.mail import send_email


def _register(client, name: str, email: str, password: str = "password123"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_join_closed_group_rejected(client):
    owner = _register(client, "Owner", "owner@example.com")
    guest = _register(client, "Guest", "guest@example.com")
    oh = _auth(owner["access_token"])
    gh = _auth(guest["access_token"])

    group = client.post(
        "/api/groups",
        headers=oh,
        json={"name": "ClosedSoon", "currency": "USD", "reminder_days": 7},
    ).json()
    assert client.post(f"/api/groups/{group['id']}/close", headers=oh).status_code == 200
    res = client.post(f"/api/groups/join/{group['invite_token']}", headers=gh)
    assert res.status_code == 400
    assert "closed" in res.json()["detail"].lower()


def test_expense_mutation_requires_payer_creator_or_owner(client):
    alice = _register(client, "Alice", "a2@example.com")
    bob = _register(client, "Bob", "b2@example.com")
    cara = _register(client, "Cara", "c2@example.com")
    ah, bh, ch = _auth(alice["access_token"]), _auth(bob["access_token"]), _auth(cara["access_token"])

    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "AuthZ", "currency": "USD", "reminder_days": 7},
    ).json()
    token = group["invite_token"]
    gid = group["id"]
    assert client.post(f"/api/groups/join/{token}", headers=bh).status_code == 200
    assert client.post(f"/api/groups/join/{token}", headers=ch).status_code == 200

    expense = client.post(
        f"/api/groups/{gid}/expenses",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 300,
            "split_type": "equal",
            "participants": [
                {"user_id": alice["user"]["id"]},
                {"user_id": bob["user"]["id"]},
                {"user_id": cara["user"]["id"]},
            ],
            "category": "food",
            "expense_date": "2026-10-01",
        },
    )
    assert expense.status_code == 200
    eid = expense.json()["id"]

    denied = client.delete(f"/api/expenses/{eid}", headers=bh)
    assert denied.status_code == 403

    updated = client.patch(
        f"/api/expenses/{eid}",
        headers=ah,
        json={"comment": "updated note"},
    )
    assert updated.status_code == 200
    assert updated.json()["comment"] == "updated note"
    assert updated.json()["created_by_id"] == alice["user"]["id"]


def test_settlement_capped_to_debt(client):
    alice = _register(client, "Alice", "a3@example.com")
    bob = _register(client, "Bob", "b3@example.com")
    ah, bh = _auth(alice["access_token"]), _auth(bob["access_token"])
    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "Cap", "currency": "USD", "reminder_days": 7},
    ).json()
    gid = group["id"]
    assert client.post(f"/api/groups/join/{group['invite_token']}", headers=bh).status_code == 200

    client.post(
        f"/api/groups/{gid}/expenses",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 1000,
            "split_type": "equal",
            "participants": [{"user_id": alice["user"]["id"]}, {"user_id": bob["user"]["id"]}],
            "category": "food",
            "expense_date": "2026-10-01",
        },
    )
    balances = client.get(f"/api/groups/{gid}/balances", headers=ah).json()
    transfer = balances["suggested_transfers"][0]
    over = client.post(
        f"/api/groups/{gid}/settlements",
        headers=bh,
        json={
            "from_user_id": transfer["from_user_id"],
            "to_user_id": transfer["to_user_id"],
            "amount_cents": transfer["amount_cents"] + 1,
        },
    )
    assert over.status_code == 400


def test_receipt_requires_auth_and_validates_type(client):
    alice = _register(client, "Alice", "a4@example.com")
    ah = _auth(alice["access_token"])
    group = client.post(
        "/api/groups",
        headers=ah,
        json={"name": "Receipts", "currency": "USD", "reminder_days": 7},
    ).json()
    gid = group["id"]
    expense = client.post(
        f"/api/groups/{gid}/expenses",
        headers=ah,
        json={
            "payer_id": alice["user"]["id"],
            "amount_cents": 100,
            "split_type": "equal",
            "participants": [{"user_id": alice["user"]["id"]}],
            "category": "food",
            "expense_date": "2026-10-01",
        },
    ).json()
    eid = expense["id"]

    bad = client.post(
        f"/api/expenses/{eid}/receipt",
        headers=ah,
        files={"file": ("note.exe", BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert bad.status_code == 400

    ok = client.post(
        f"/api/expenses/{eid}/receipt",
        headers=ah,
        files={"file": ("receipt.png", BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
    )
    assert ok.status_code == 200
    assert ok.json()["receipt_path"]

    client.cookies.clear()
    unauth = client.get(f"/api/expenses/{eid}/receipt")
    assert unauth.status_code == 401

    download = client.get(f"/api/expenses/{eid}/receipt", headers=ah)
    assert download.status_code == 200


def test_smtp_backend_sends_via_smtplib(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pass")
    monkeypatch.setenv("SMTP_FROM", "from@example.com")
    monkeypatch.setenv("SMTP_TLS", "true")
    get_settings.cache_clear()
    try:
        smtp_instance = MagicMock()
        smtp_cm = MagicMock()
        smtp_cm.__enter__.return_value = smtp_instance
        smtp_cm.__exit__.return_value = False
        with patch("app.services.mail.smtplib.SMTP", return_value=smtp_cm) as smtp_ctor:
            assert send_email("to@example.com", "Hi", "Body") is None
            smtp_ctor.assert_called_once()
            smtp_instance.starttls.assert_called_once()
            smtp_instance.login.assert_called_once_with("user", "pass")
            smtp_instance.send_message.assert_called_once()
    finally:
        get_settings.cache_clear()


def test_refresh_and_logout_cookies(client):
    created = _register(client, "Cookie", "cookie@example.com")
    assert created["access_token"]
    assert client.cookies.get("se_access")
    assert client.cookies.get("se_refresh")

    me = client.get("/api/auth/me")
    assert me.status_code == 200

    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    out = client.post("/api/auth/logout")
    assert out.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
