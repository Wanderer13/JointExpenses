"""Admin-only endpoints: users, roles, clear-linked, action logs."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.constants import DEFAULT_ACTION_LOG_LIMIT, MAX_ACTION_LOG_LIMIT
from app.database import get_db
from app.deps import require_admin
from app.models import AdminActionLog, User
from app.schemas import (
    AdminActionLogOut,
    AdminRoleUpdate,
    AdminUserOut,
    ClearLinkedUsersOut,
)
from app.services.admin_user_service import clear_linked_users, list_admin_users, set_user_role

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        has_password=user.password_hash is not None,
        google_linked=user.google_sub is not None,
    )


def _action_log_out(row: AdminActionLog) -> AdminActionLogOut:
    try:
        payload = json.loads(row.payload or "{}")
    except json.JSONDecodeError:
        payload = {}
    return AdminActionLogOut(
        id=row.id,
        actor_id=row.actor_id,
        actor_email=row.actor_email,
        action=row.action,
        target_type=row.target_type,
        target_id=row.target_id,
        payload=payload if isinstance(payload, dict) else {},
        created_at=row.created_at,
    )


@router.get("/users", response_model=list[AdminUserOut])
def admin_list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdminUserOut]:
    _ = admin
    return [_admin_user_out(u) for u in list_admin_users(db)]


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
def admin_set_role(
    user_id: int,
    payload: AdminRoleUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    updated = set_user_role(db, actor=admin, target=target, new_role=payload.role)
    return _admin_user_out(updated)


@router.post("/users/clear-linked", response_model=ClearLinkedUsersOut)
def admin_clear_linked(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ClearLinkedUsersOut:
    deleted_ids, count = clear_linked_users(db, actor=admin)
    return ClearLinkedUsersOut(deleted_user_ids=deleted_ids, deleted_count=count)


@router.get("/action-logs", response_model=list[AdminActionLogOut])
def admin_action_logs(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_ACTION_LOG_LIMIT, ge=1, le=MAX_ACTION_LOG_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> list[AdminActionLogOut]:
    _ = admin
    rows = (
        db.query(AdminActionLog)
        .order_by(AdminActionLog.created_at.desc(), AdminActionLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_action_log_out(r) for r in rows]
