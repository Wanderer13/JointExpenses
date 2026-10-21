import json
from pathlib import Path

from app.config import get_settings
from app.services.mail_stub import send_email


def test_send_email_writes_outbox(tmp_path, monkeypatch):
    monkeypatch.setenv("MAIL_OUTBOX_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        path = send_email(
            to="debtor@example.com",
            subject="Reminder",
            body="Please pay",
            body_html="<p>Please pay</p>",
            meta={"group_id": 1, "join_url": "http://127.0.0.1:5173/join/abc"},
        )
        assert path.exists()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["to"] == "debtor@example.com"
        assert data["subject"] == "Reminder"
        assert data["body_html"] == "<p>Please pay</p>"
        assert data["meta"]["group_id"] == 1
        assert data["meta"]["join_url"].endswith("/join/abc")
    finally:
        get_settings.cache_clear()
