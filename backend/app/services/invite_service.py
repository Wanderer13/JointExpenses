"""Pending email invites and join URL helpers."""

from __future__ import annotations

from html import escape

from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import EventType
from app.models import Group, GroupMember, GroupStatus, MemberRole, PendingInvite, User
from app.services.activity_service import log_activity


def build_join_url(invite_token: str) -> str:
    return f"{get_settings().public_frontend_url}/join/{invite_token}"


def invite_email_bodies(inviter_name: str, group_name: str, join_url: str, invite_token: str) -> tuple[str, str]:
    text = (
        f'{inviter_name} invited you to "{group_name}".\n\n'
        f"Join here:\n{join_url}\n\n"
        f"Or open the app and join with token: {invite_token}\n"
    )
    safe_inviter = escape(inviter_name)
    safe_group = escape(group_name)
    safe_url = escape(join_url, quote=True)
    html = (
        f"<p>{safe_inviter} invited you to &quot;{safe_group}&quot;.</p>"
        f'<p><a href="{safe_url}">Join the group</a></p>'
        f"<p>Or open the app and join with token: <code>{escape(invite_token)}</code></p>"
    )
    return text, html


def upsert_pending_invite(db: Session, group_id: int, email: str) -> PendingInvite:
    email = email.lower()
    existing = (
        db.query(PendingInvite)
        .filter(PendingInvite.group_id == group_id, PendingInvite.email == email)
        .first()
    )
    if existing:
        return existing
    row = PendingInvite(group_id=group_id, email=email)
    db.add(row)
    db.flush()
    return row


def ensure_invited_member(db: Session, group: Group, email: str) -> User:
    """Find or create a user for the invite email and add them to the group now.

    Invited people can be included in expenses before they register. They claim the
    account later via register (set password) or Google Sign-In.
    """
    email = email.lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        local = email.split("@")[0][:120] or "guest"
        user = User(email=email, name=local, password_hash=None)
        db.add(user)
        db.flush()
    membership = (
        db.query(GroupMember)
        .filter(GroupMember.group_id == group.id, GroupMember.user_id == user.id)
        .first()
    )
    if membership is None:
        db.add(GroupMember(group_id=group.id, user_id=user.id, role=MemberRole.member))
        db.flush()
        log_activity(
            db,
            group_id=group.id,
            actor_id=None,
            event_type=EventType.MEMBER_JOINED,
            payload={"user_id": user.id, "name": user.name, "via": "email_invite"},
        )
    return user


def clear_pending_invite(db: Session, group_id: int, email: str) -> None:
    db.query(PendingInvite).filter(
        PendingInvite.group_id == group_id,
        PendingInvite.email == email.lower(),
    ).delete(synchronize_session=False)


def accept_pending_invites(db: Session, user: User) -> int:
    """Join open groups with pending invites for this email. Leave closed-group invites pending."""
    email = user.email.lower()
    pending = (
        db.query(PendingInvite)
        .filter(PendingInvite.email == email)
        .all()
    )
    joined = 0
    for invite in pending:
        group = db.query(Group).filter(Group.id == invite.group_id).first()
        if group is None:
            db.delete(invite)
            continue
        if group.status == GroupStatus.closed:
            continue
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
                event_type=EventType.MEMBER_JOINED,
                payload={"user_id": user.id, "name": user.name, "via": "pending_invite"},
            )
            joined += 1
        db.delete(invite)
    return joined
