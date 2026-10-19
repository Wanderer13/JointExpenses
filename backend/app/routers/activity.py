from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.models import ActivityEvent, User
from app.schemas import ActivityOut

router = APIRouter(tags=["activity"])


@router.get("/groups/{group_id}/activity", response_model=list[ActivityOut])
def group_activity(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ActivityOut]:
    get_membership(db, group_id, user.id)
    events = (
        db.query(ActivityEvent)
        .options(joinedload(ActivityEvent.actor))
        .filter(ActivityEvent.group_id == group_id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(100)
        .all()
    )
    result = []
    for e in events:
        try:
            payload = json.loads(e.payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        result.append(
            ActivityOut(
                id=e.id,
                group_id=e.group_id,
                actor_id=e.actor_id,
                actor_name=e.actor.name if e.actor else None,
                event_type=e.event_type,
                payload=payload,
                created_at=e.created_at,
            )
        )
    return result
