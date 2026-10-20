from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, get_group_or_404, get_membership
from app.models import Group, GroupMember, GroupStatus, MemberRole, User
from app.schemas import (
    GroupCreate,
    GroupOut,
    GroupUpdate,
    InviteEmailIn,
    MemberOut,
    MessageOut,
)
from app.services.activity_service import log_activity
from app.services.mail import send_email
from app.services.reminder_service import send_group_close_report
from app.ws import manager

router = APIRouter(prefix="/groups", tags=["groups"])


def _member_out(m: GroupMember) -> MemberOut:
    return MemberOut(user_id=m.user_id, role=m.role, name=m.user.name, email=m.user.email)


def _group_out(group: Group) -> GroupOut:
    return GroupOut(
        id=group.id,
        name=group.name,
        currency=group.currency,
        reminder_days=group.reminder_days,
        status=group.status,
        invite_token=group.invite_token,
        created_at=group.created_at,
        members=[_member_out(m) for m in group.members],
    )


def _load_group(db: Session, group_id: int) -> Group:
    group = (
        db.query(Group)
        .options(joinedload(Group.members).joinedload(GroupMember.user))
        .filter(Group.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.get("", response_model=list[GroupOut])
def list_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[GroupOut]:
    memberships = (
        db.query(GroupMember)
        .options(joinedload(GroupMember.group).joinedload(Group.members).joinedload(GroupMember.user))
        .filter(GroupMember.user_id == user.id)
        .all()
    )
    return [_group_out(m.group) for m in memberships]


@router.post("", response_model=GroupOut)
def create_group(
    payload: GroupCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    group = Group(
        name=payload.name.strip(),
        currency=payload.currency.upper(),
        reminder_days=payload.reminder_days,
        status=GroupStatus.open,
        invite_token=secrets.token_urlsafe(24),
        created_by_id=user.id,
    )
    db.add(group)
    db.flush()
    db.add(GroupMember(group_id=group.id, user_id=user.id, role=MemberRole.owner))
    log_activity(
        db,
        group_id=group.id,
        actor_id=user.id,
        event_type="group_created",
        payload={"name": group.name},
    )
    db.commit()
    return _group_out(_load_group(db, group.id))


@router.get("/{group_id}", response_model=GroupOut)
def get_group(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    get_membership(db, group_id, user.id)
    return _group_out(_load_group(db, group_id))


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(
    group_id: int,
    payload: GroupUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    membership = get_membership(db, group_id, user.id)
    if membership.role != MemberRole.owner:
        raise HTTPException(status_code=403, detail="Only owner can update group")
    group = get_group_or_404(db, group_id)
    if payload.name is not None:
        group.name = payload.name.strip()
    if payload.currency is not None:
        group.currency = payload.currency.upper()
    if payload.reminder_days is not None:
        group.reminder_days = payload.reminder_days
    db.commit()
    return _group_out(_load_group(db, group_id))


@router.post("/join/{invite_token}", response_model=GroupOut)
def join_by_token(
    invite_token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    group = db.query(Group).filter(Group.invite_token == invite_token).first()
    if not group:
        raise HTTPException(status_code=404, detail="Invite not found")
    if group.status == GroupStatus.closed:
        raise HTTPException(status_code=400, detail="Group is closed")
    existing = (
        db.query(GroupMember)
        .filter(GroupMember.group_id == group.id, GroupMember.user_id == user.id)
        .first()
    )
    if not existing:
        db.add(GroupMember(group_id=group.id, user_id=user.id, role=MemberRole.member))
        log_activity(
            db,
            group_id=group.id,
            actor_id=user.id,
            event_type="member_joined",
            payload={"user_id": user.id, "name": user.name},
        )
        db.commit()
    return _group_out(_load_group(db, group.id))


@router.post("/{group_id}/invite-email", response_model=MessageOut)
def invite_by_email(
    group_id: int,
    payload: InviteEmailIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    get_membership(db, group_id, user.id)
    group = get_group_or_404(db, group_id)
    send_email(
        to=payload.email.lower(),
        subject=f'Invitation to group "{group.name}"',
        body=(
            f'{user.name} invited you to "{group.name}".\n'
            f"Open the app and join with token: {group.invite_token}\n"
            f"Or use path /join/{group.invite_token}\n"
        ),
        meta={"group_id": group.id, "invite_token": group.invite_token},
    )
    log_activity(
        db,
        group_id=group.id,
        actor_id=user.id,
        event_type="invite_sent",
        payload={"email": payload.email.lower()},
    )
    db.commit()
    return MessageOut(message="Invite email sent")


@router.post("/{group_id}/close", response_model=GroupOut)
async def close_group(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    membership = get_membership(db, group_id, user.id)
    if membership.role != MemberRole.owner:
        raise HTTPException(status_code=403, detail="Only owner can close group")
    group = get_group_or_404(db, group_id)
    if group.status == GroupStatus.closed:
        return _group_out(_load_group(db, group_id))
    group.status = GroupStatus.closed
    send_group_close_report(db, group)
    log_activity(
        db,
        group_id=group.id,
        actor_id=user.id,
        event_type="group_closed",
        payload={},
    )
    db.commit()
    await manager.broadcast(group_id, {"type": "group_updated", "group_id": group_id})
    return _group_out(_load_group(db, group_id))


@router.post("/{group_id}/reopen", response_model=GroupOut)
async def reopen_group(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    membership = get_membership(db, group_id, user.id)
    if membership.role != MemberRole.owner:
        raise HTTPException(status_code=403, detail="Only owner can reopen group")
    group = get_group_or_404(db, group_id)
    group.status = GroupStatus.open
    log_activity(
        db,
        group_id=group.id,
        actor_id=user.id,
        event_type="group_reopened",
        payload={},
    )
    db.commit()
    await manager.broadcast(group_id, {"type": "group_updated", "group_id": group_id})
    return _group_out(_load_group(db, group_id))
