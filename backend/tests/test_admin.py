from __future__ import annotations

from app.config import get_settings
from app.constants import DEFAULT_SEED_EMAILS
from app.models import AppRole, User
from app.security import hash_password


def _register(client, name: str, email: str, password: str = "password123"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_admin(db, email: str) -> User:
    user = db.query(User).filter(User.email == email.lower()).first()
    assert user is not None
    user.role = AppRole.admin
    db.commit()
    db.refresh(user)
    return user


def test_admin_endpoints_require_admin(client):
    user = _register(client, "Norm", "norm@example.org")
    headers = _auth(user["access_token"])
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.get("/api/admin/action-logs", headers=headers).status_code == 403
    assert client.post("/api/admin/users/clear-linked", headers=headers).status_code == 403


def test_register_creates_action_log(client, db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin-reader@example.com")
    get_settings.cache_clear()
    try:
        created = _register(client, "Loggy", "loggy@example.org")
        assert created["user"]["role"] == "user"
        admin = _register(client, "AdminReader", "admin-reader@example.com")
        assert admin["user"]["role"] == "admin"
        logs = client.get("/api/admin/action-logs", headers=_auth(admin["access_token"]))
        assert logs.status_code == 200
        assert any(
            row["action"] == "user.register" and row["actor_email"] == "loggy@example.org"
            for row in logs.json()
        )
        _ = db  # same engine; keep fixture for consistency with other admin tests
    finally:
        get_settings.cache_clear()


def test_admin_list_role_clear_and_logs(client, db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    get_settings.cache_clear()
    try:
        boss = _register(client, "Boss", "boss@example.com")
        assert boss["user"]["role"] == "admin"
        bh = _auth(boss["access_token"])

        other = _register(client, "Other", "other@test.com")
        assert other["user"]["role"] == "user"

        # seed defaults (protected)
        for email, name in [
            ("alice@example.com", "Alice"),
            ("bob@example.com", "Bob"),
            ("cara@example.com", "Cara"),
        ]:
            db.add(
                User(
                    email=email,
                    name=name,
                    password_hash=hash_password("password123"),
                    role=AppRole.user,
                )
            )
        db.commit()

        listed = client.get("/api/admin/users", headers=bh)
        assert listed.status_code == 200
        emails = {u["email"] for u in listed.json()}
        assert "boss@example.com" in emails
        assert "other@test.com" in emails

        logs = client.get("/api/admin/action-logs", headers=bh)
        assert logs.status_code == 200
        actions = {row["action"] for row in logs.json()}
        assert "user.register" in actions

        other_id = other["user"]["id"]
        promoted = client.patch(
            f"/api/admin/users/{other_id}/role",
            headers=bh,
            json={"role": "admin"},
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "admin"

        demoted = client.patch(
            f"/api/admin/users/{boss['user']['id']}/role",
            headers=bh,
            json={"role": "user"},
        )
        assert demoted.status_code == 200

        _make_admin(db, "boss@example.com")
        clear = client.post("/api/admin/users/clear-linked", headers=bh)
        assert clear.status_code == 200, clear.text
        body = clear.json()
        assert body["deleted_count"] >= 1

        remaining = {u["email"] for u in client.get("/api/admin/users", headers=bh).json()}
        assert DEFAULT_SEED_EMAILS.issubset(remaining)
        assert "boss@example.com" in remaining
        assert "other@test.com" not in remaining
    finally:
        get_settings.cache_clear()


def test_cannot_demote_last_admin(client, db):
    admin = _register(client, "Solo", "solo-admin@example.com")
    _make_admin(db, "solo-admin@example.com")
    headers = _auth(admin["access_token"])
    res = client.patch(
        f"/api/admin/users/{admin['user']['id']}/role",
        headers=headers,
        json={"role": "user"},
    )
    assert res.status_code == 400
    assert "last admin" in res.json()["detail"].lower()


def test_clear_linked_with_notifications_and_tokens(client, db, monkeypatch):
    """Regression: ORM must not nullify notifications.user_id (NOT NULL)."""
    monkeypatch.setenv("ADMIN_EMAILS", "cleaner@example.com")
    get_settings.cache_clear()
    try:
        from app.models import Notification
        from app.security import issue_refresh_token

        boss = _register(client, "Cleaner", "cleaner@example.com")
        target = _register(client, "Doomed", "doomed@example.com")
        doomed = db.query(User).filter(User.email == "doomed@example.com").first()
        assert doomed is not None
        doomed_id = doomed.id
        db.add(
            Notification(
                user_id=doomed_id,
                notification_type="test",
                payload="{}",
            )
        )
        issue_refresh_token(db, doomed_id)
        db.commit()

        clear = client.post(
            "/api/admin/users/clear-linked",
            headers=_auth(boss["access_token"]),
        )
        assert clear.status_code == 200, clear.text
        assert clear.json()["deleted_count"] >= 1
        db.expire_all()
        assert db.query(User).filter(User.email == "doomed@example.com").first() is None
        assert db.query(Notification).filter(Notification.user_id == doomed_id).count() == 0
    finally:
        get_settings.cache_clear()
