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
            meta={"group_id": 1},
        )
        assert path.exists()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["to"] == "debtor@example.com"
        assert data["subject"] == "Reminder"
        assert data["meta"]["group_id"] == 1
    finally:
        get_settings.cache_clear()
