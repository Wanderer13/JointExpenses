"""Balance calculation and debt simplification."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.models import Expense, Group, GroupMember, Settlement, SettlementStatus, User


def compute_net_balances(db: Session, group_id: int) -> dict[int, int]:
    """Net balance per user in cents. Positive = others owe them; negative = they owe."""
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    nets: dict[int, int] = {m.user_id: 0 for m in members}

    expenses = (
        db.query(Expense)
        .options(joinedload(Expense.splits))
        .filter(Expense.group_id == group_id)
        .all()
    )
    for expense in expenses:
        if expense.payer_id not in nets:
            nets[expense.payer_id] = 0
        nets[expense.payer_id] += expense.amount_cents
        for split in expense.splits:
            if split.user_id not in nets:
                nets[split.user_id] = 0
            nets[split.user_id] -= split.amount_cents

    settlements = (
        db.query(Settlement)
        .filter(
            Settlement.group_id == group_id,
            Settlement.status == SettlementStatus.confirmed,
        )
        .all()
    )
    for s in settlements:
        if s.from_user_id not in nets:
            nets[s.from_user_id] = 0
        if s.to_user_id not in nets:
            nets[s.to_user_id] = 0
        # Debtor paid creditor: debtor's debt decreases (balance up), creditor's credit decreases
        nets[s.from_user_id] += s.amount_cents
        nets[s.to_user_id] -= s.amount_cents

    return nets


def simplify_debts(nets: dict[int, int]) -> list[tuple[int, int, int]]:
    """Greedy debt simplification. Returns (from_user_id, to_user_id, amount_cents)."""
    debtors = sorted([(uid, -bal) for uid, bal in nets.items() if bal < 0], key=lambda x: x[1], reverse=True)
    creditors = sorted([(uid, bal) for uid, bal in nets.items() if bal > 0], key=lambda x: x[1], reverse=True)

    transfers: list[tuple[int, int, int]] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        d_id, d_amt = debtors[i]
        c_id, c_amt = creditors[j]
        pay = min(d_amt, c_amt)
        if pay > 0:
            transfers.append((d_id, c_id, pay))
        debtors[i] = (d_id, d_amt - pay)
        creditors[j] = (c_id, c_amt - pay)
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return transfers


def group_balances_payload(db: Session, group: Group) -> dict:
    nets = compute_net_balances(db, group.id)
    users = {u.id: u for u in db.query(User).filter(User.id.in_(nets.keys())).all()} if nets else {}
    transfers = simplify_debts(nets)
    return {
        "group_id": group.id,
        "currency": group.currency,
        "nets": [
            {
                "user_id": uid,
                "name": users[uid].name if uid in users else str(uid),
                "email": users[uid].email if uid in users else None,
                "balance_cents": bal,
            }
            for uid, bal in sorted(nets.items(), key=lambda x: x[0])
        ],
        "suggested_transfers": [
            {
                "from_user_id": f,
                "from_name": users[f].name if f in users else str(f),
                "from_email": users[f].email if f in users else None,
                "to_user_id": t,
                "to_name": users[t].name if t in users else str(t),
                "to_email": users[t].email if t in users else None,
                "amount_cents": amt,
            }
            for f, t, amt in transfers
        ],
        "sum_check": sum(nets.values()),
    }


def user_balances_across_groups(db: Session, user_id: int) -> list[dict]:
    memberships = (
        db.query(GroupMember)
        .options(joinedload(GroupMember.group))
        .filter(GroupMember.user_id == user_id)
        .all()
    )
    result = []
    for m in memberships:
        nets = compute_net_balances(db, m.group_id)
        result.append(
            {
                "group_id": m.group_id,
                "group_name": m.group.name,
                "currency": m.group.currency,
                "balance_cents": nets.get(user_id, 0),
            }
        )
    return result


def oldest_debt_age_days(db: Session, group_id: int, debtor_id: int, creditor_id: int) -> int | None:
    """Approximate debt age from earliest expense where debtor owes creditor net contribution."""
    from datetime import date

    # Use earliest unpaid expense date involving both as a simple heuristic:
    # if suggested transfer exists, age from oldest expense in group where debtor has a split and creditor paid.
    expenses = (
        db.query(Expense)
        .options(joinedload(Expense.splits))
        .filter(Expense.group_id == group_id)
        .order_by(Expense.expense_date.asc())
        .all()
    )
    for expense in expenses:
        if expense.payer_id != creditor_id:
            continue
        for split in expense.splits:
            if split.user_id == debtor_id and split.amount_cents > 0:
                return (date.today() - expense.expense_date).days
    return None
