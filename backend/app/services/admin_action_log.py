"""App-wide audit log of user actions for the admin panel."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import AdminActionLog, User


def log_user_action(
    db: Session,
    *,
    actor: User | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    payload: dict | None = None,
) -> AdminActionLog:
    entry = AdminActionLog(
        actor_id=actor.id if actor is not None else None,
        actor_email=actor.email if actor is not None else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=json.dumps(payload or {}, ensure_ascii=False),
    )
    db.add(entry)
    return entry
