"""Home overview aggregates for the current user."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Expense,
    ExpenseStatus,
    Group,
    GroupMember,
    Settlement,
    SettlementStatus,
    User,
)
from app.services.balance_service import user_balances_across_groups


def build_overview(db: Session, user: User) -> dict:
    memberships = (
        db.query(GroupMember)
        .options(joinedload(GroupMember.group))
        .filter(GroupMember.user_id == user.id)
        .all()
    )
    group_ids = [m.group_id for m in memberships]
    groups_by_id = {m.group_id: m.group for m in memberships}

    pending_settlements = _pending_settlements(db, user, group_ids, groups_by_id)
    group_balances = user_balances_across_groups(db, user.id)
    balances_by_currency = _balances_by_currency(group_balances)
    open_expenses = _open_expenses(db, user.id, group_ids, groups_by_id)

    return {
        "pending_settlements": pending_settlements,
        "balances_by_currency": balances_by_currency,
        "group_balances": group_balances,
        "open_expenses": open_expenses,
        "pending_settlement_count": len(pending_settlements),
    }


def _pending_settlements(
    db: Session,
    user: User,
    group_ids: list[int],
    groups_by_id: dict[int, Group],
) -> list[dict]:
    if not group_ids:
        return []
    rows = (
        db.query(Settlement)
        .options(joinedload(Settlement.from_user), joinedload(Settlement.to_user))
        .filter(
            Settlement.group_id.in_(group_ids),
            Settlement.status == SettlementStatus.pending,
            or_(Settlement.from_user_id == user.id, Settlement.to_user_id == user.id),
        )
        .order_by(Settlement.created_at.desc())
        .all()
    )
    result = []
    for s in rows:
        group = groups_by_id.get(s.group_id)
        if not group or not s.from_user or not s.to_user:
            continue
        is_from = s.from_user_id == user.id
        counterpart = s.to_user if is_from else s.from_user
        result.append(
            {
                "id": s.id,
                "group_id": s.group_id,
                "group_name": group.name,
                "currency": group.currency,
                "from_user_id": s.from_user_id,
                "to_user_id": s.to_user_id,
                "amount_cents": s.amount_cents,
                "status": s.status,
                "created_at": s.created_at,
                "from_name": s.from_user.name,
                "from_email": s.from_user.email,
                "to_name": s.to_user.name,
                "to_email": s.to_user.email,
                "counterpart_user_id": counterpart.id,
                "counterpart_name": counterpart.name,
                "counterpart_email": counterpart.email,
                "needs_my_action": True,
            }
        )
    return result


def _balances_by_currency(group_balances: list[dict]) -> list[dict]:
    by_currency: dict[str, dict[str, int]] = defaultdict(
        lambda: {"you_owe_cents": 0, "owed_to_you_cents": 0}
    )
    for item in group_balances:
        currency = item["currency"]
        bal = item["balance_cents"]
        if bal < 0:
            by_currency[currency]["you_owe_cents"] += -bal
        elif bal > 0:
            by_currency[currency]["owed_to_you_cents"] += bal
    return [
        {
            "currency": currency,
            "you_owe_cents": totals["you_owe_cents"],
            "owed_to_you_cents": totals["owed_to_you_cents"],
        }
        for currency, totals in sorted(by_currency.items())
    ]


def _open_expenses(
    db: Session,
    user_id: int,
    group_ids: list[int],
    groups_by_id: dict[int, Group],
) -> list[dict]:
    if not group_ids:
        return []
    expenses = (
        db.query(Expense)
        .options(
            joinedload(Expense.payer),
            joinedload(Expense.splits),
        )
        .filter(
            Expense.group_id.in_(group_ids),
            Expense.status == ExpenseStatus.open,
        )
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .all()
    )
    result = []
    for expense in expenses:
        involved = expense.payer_id == user_id or any(
            s.user_id == user_id for s in expense.splits
        )
        if not involved:
            continue
        group = groups_by_id.get(expense.group_id)
        if not group or not expense.payer:
            continue
        result.append(
            {
                "id": expense.id,
                "group_id": expense.group_id,
                "group_name": group.name,
                "currency": group.currency,
                "category": expense.category,
                "amount_cents": expense.amount_cents,
                "expense_date": expense.expense_date,
                "payer_id": expense.payer_id,
                "payer_name": expense.payer.name,
                "payer_email": expense.payer.email,
            }
        )
    return result


def shared_group_ids(db: Session, user_a_id: int, user_b_id: int) -> set[int]:
    a_ids = {
        m.group_id
        for m in db.query(GroupMember).filter(GroupMember.user_id == user_a_id).all()
    }
    b_ids = {
        m.group_id
        for m in db.query(GroupMember).filter(GroupMember.user_id == user_b_id).all()
    }
    return a_ids & b_ids


def build_user_profile(db: Session, viewer: User, target_id: int) -> dict | None:
    target = db.query(User).filter(User.id == target_id).first()
    if not target:
        return None
    if viewer.id == target.id:
        memberships = (
            db.query(GroupMember)
            .options(joinedload(GroupMember.group))
            .filter(GroupMember.user_id == viewer.id)
            .all()
        )
        shared = [m.group for m in memberships if m.group]
    else:
        ids = shared_group_ids(db, viewer.id, target.id)
        if not ids:
            return None
        shared = db.query(Group).filter(Group.id.in_(ids)).order_by(Group.name).all()
    return {
        "id": target.id,
        "name": target.name,
        "email": target.email,
        "shared_groups": [
            {
                "id": g.id,
                "name": g.name,
                "currency": g.currency,
                "status": g.status,
            }
            for g in sorted(shared, key=lambda g: g.name.lower())
        ],
    }
