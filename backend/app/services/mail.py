from __future__ import annotations

import json
import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from app.config import get_settings
from app.constants import MAIL_BACKEND_SMTP, MAIL_BACKEND_STUB

logger = logging.getLogger(__name__)


def send_email(
    to: str,
    subject: str,
    body: str,
    meta: dict | None = None,
    *,
    body_html: str | None = None,
) -> Path | None:
    settings = get_settings()
    backend = (settings.mail_backend or MAIL_BACKEND_STUB).lower()
    if backend == MAIL_BACKEND_SMTP:
        _send_smtp(to, subject, body, body_html=body_html)
        return None
    return _send_stub(to, subject, body, meta, body_html=body_html)


def _send_stub(
    to: str,
    subject: str,
    body: str,
    meta: dict | None,
    *,
    body_html: str | None = None,
) -> Path:
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
        "body_html": body_html,
        "meta": meta or {},
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("mail-stub to=%s subject=%r -> %s", to, subject, path)
    return path


def _send_smtp(to: str, subject: str, body: str, *, body_html: str | None = None) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or "noreply@localhost"
    msg["To"] = to
    msg.set_content(body)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    if settings.smtp_tls:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    logger.info("smtp mail to=%s subject=%r", to, subject)
