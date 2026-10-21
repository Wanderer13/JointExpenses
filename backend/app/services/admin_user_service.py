"""Admin user management: list, role changes, clear non-default users."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.constants import DEFAULT_SEED_EMAILS
from app.models import (
    ActivityEvent,
    AdminActionLog,
    AppRole,
    Expense,
    ExpenseSplit,
    Group,
    GroupMember,
    ReminderSent,
    Settlement,
    User,
)
from app.services.admin_action_log import log_user_action


def list_admin_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id.asc()).all()


def set_user_role(db: Session, *, actor: User, target: User, new_role: AppRole) -> User:
    if target.role == new_role:
        return target

    if new_role == AppRole.user and target.role == AppRole.admin:
        admin_count = db.query(User).filter(User.role == AppRole.admin).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last admin")

    old_role = target.role
    target.role = new_role
    log_user_action(
        db,
        actor=actor,
        action="admin.set_role",
        target_type="user",
        target_id=target.id,
        payload={
            "email": target.email,
            "old_role": old_role.value,
            "new_role": new_role.value,
        },
    )
    db.commit()
    db.refresh(target)
    return target


def clear_linked_users(db: Session, *, actor: User) -> tuple[list[int], int]:
    victims = (
        db.query(User)
        .filter(
            ~User.email.in_(DEFAULT_SEED_EMAILS),
            User.id != actor.id,
        )
        .all()
    )
    victim_ids = [u.id for u in victims]
    if not victim_ids:
        log_user_action(
            db,
            actor=actor,
            action="admin.clear_linked",
            payload={"deleted_count": 0, "deleted_user_ids": []},
        )
        db.commit()
        return [], 0

    # 1. Groups created by victims (cascade members/expenses/settlements/activity)
    victim_groups = db.query(Group).filter(Group.created_by_id.in_(victim_ids)).all()
    for group in victim_groups:
        db.delete(group)
    db.flush()

    # 2. Remaining rows that still reference victims
    expenses = (
        db.query(Expense)
        .filter(or_(Expense.payer_id.in_(victim_ids), Expense.created_by_id.in_(victim_ids)))
        .all()
    )
    for expense in expenses:
        db.delete(expense)
    db.flush()

    db.query(ExpenseSplit).filter(ExpenseSplit.user_id.in_(victim_ids)).delete(
        synchronize_session=False
    )
    db.query(Settlement).filter(
        or_(Settlement.from_user_id.in_(victim_ids), Settlement.to_user_id.in_(victim_ids))
    ).delete(synchronize_session=False)
    db.query(ReminderSent).filter(
        or_(ReminderSent.debtor_id.in_(victim_ids), ReminderSent.creditor_id.in_(victim_ids))
    ).delete(synchronize_session=False)
    db.query(ActivityEvent).filter(ActivityEvent.actor_id.in_(victim_ids)).update(
        {ActivityEvent.actor_id: None},
        synchronize_session=False,
    )
    db.query(GroupMember).filter(GroupMember.user_id.in_(victim_ids)).delete(
        synchronize_session=False
    )
    db.query(AdminActionLog).filter(AdminActionLog.actor_id.in_(victim_ids)).update(
        {AdminActionLog.actor_id: None},
        synchronize_session=False,
    )
    db.flush()

    for user in victims:
        db.delete(user)
    db.flush()

    log_user_action(
        db,
        actor=actor,
        action="admin.clear_linked",
        payload={"deleted_count": len(victim_ids), "deleted_user_ids": victim_ids},
    )
    db.commit()
    return victim_ids, len(victim_ids)
