from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings


def send_email(to: str, subject: str, body: str, meta: dict | None = None) -> Path:
    settings = get_settings()
    outbox = Path(settings.mail_outbox_dir)
    outbox.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    safe_to = to.replace("@", "_at_").replace(".", "_")
    path = outbox / f"{ts}_{safe_to}.json"
    payload = {
        "to": to,
        "subject": subject,
        "body": body,
        "meta": meta or {},
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[mail-stub] to={to} subject={subject!r} -> {path}")
    return path
