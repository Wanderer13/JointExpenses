from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import ActivityEvent, Notification


def log_activity(
    db: Session,
    *,
    group_id: int,
    actor_id: int | None,
    event_type: str,
    payload: dict,
) -> ActivityEvent:
    event = ActivityEvent(
        group_id=group_id,
        actor_id=actor_id,
        event_type=event_type,
        payload=json.dumps(payload, ensure_ascii=False),
    )
    db.add(event)
    return event


def notify_users(
    db: Session,
    *,
    user_ids: list[int],
    notification_type: str,
    payload: dict,
) -> None:
    data = json.dumps(payload, ensure_ascii=False)
    for uid in set(user_ids):
        db.add(
            Notification(
                user_id=uid,
                notification_type=notification_type,
                payload=data,
            )
        )
