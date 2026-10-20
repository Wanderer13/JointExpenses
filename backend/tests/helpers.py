from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import Expense, ExpenseSplit, Settlement, SettlementStatus, SplitType
from app.schemas import SplitParticipantIn
from app.services.split_service import compute_split_amounts


def add_equal_expense(
    db: Session,
    *,
    group_id: int,
    payer_id: int,
    amount_cents: int,
    participant_ids: list[int],
    expense_date: date | None = None,
) -> Expense:
    amounts = compute_split_amounts(
        amount_cents,
        SplitType.equal,
        [SplitParticipantIn(user_id=uid) for uid in participant_ids],
    )
    expense = Expense(
        group_id=group_id,
        payer_id=payer_id,
        created_by_id=payer_id,
        amount_cents=amount_cents,
        split_type=SplitType.equal,
        category="test",
        expense_date=expense_date or date.today(),
        comment=None,
    )
    db.add(expense)
    db.flush()
    for uid, cents, shares in amounts:
        db.add(ExpenseSplit(expense_id=expense.id, user_id=uid, amount_cents=cents, shares=shares))
    db.commit()
    db.refresh(expense)
    return expense


def add_settlement(
    db: Session,
    *,
    group_id: int,
    from_user_id: int,
    to_user_id: int,
    amount_cents: int,
    status: SettlementStatus = SettlementStatus.pending,
) -> Settlement:
    s = Settlement(
        group_id=group_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        amount_cents=amount_cents,
        status=status,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s
