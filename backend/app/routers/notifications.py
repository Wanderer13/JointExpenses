from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.constants import FEED_PAGE_LIMIT
from app.database import get_db
from app.deps import get_current_user
from app.models import Notification, User
from app.schemas import MessageOut, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationOut]:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(FEED_PAGE_LIMIT)
        .all()
    )
    result = []
    for n in rows:
        try:
            payload = json.loads(n.payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        result.append(
            NotificationOut(
                id=n.id,
                notification_type=n.notification_type,
                payload=payload,
                read_at=n.read_at,
                created_at=n.created_at,
            )
        )
    return result


@router.post("/{notification_id}/read", response_model=MessageOut)
def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read_at = datetime.now(timezone.utc)
    db.commit()
    return MessageOut(message="ok")
