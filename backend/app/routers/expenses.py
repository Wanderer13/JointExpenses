from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, get_group_or_404, get_membership, require_expense_mutator
from app.models import Expense, ExpenseSplit, GroupMember, GroupStatus, SplitType, User
from app.schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate, SplitOut, SplitParticipantIn
from app.services.activity_service import log_activity, notify_users
from app.services.split_service import compute_split_amounts
from app.ws import manager

router = APIRouter(tags=["expenses"])

ALLOWED_RECEIPT_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def _expense_out(expense: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=expense.id,
        group_id=expense.group_id,
        payer_id=expense.payer_id,
        created_by_id=expense.created_by_id,
        amount_cents=expense.amount_cents,
        split_type=expense.split_type,
        category=expense.category,
        expense_date=expense.expense_date,
        comment=expense.comment,
        receipt_path=expense.receipt_path,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
        payer_name=expense.payer.name if expense.payer else None,
        splits=[
            SplitOut(
                user_id=s.user_id,
                amount_cents=s.amount_cents,
                shares=s.shares,
                name=s.user.name if s.user else None,
            )
            for s in expense.splits
        ],
    )


def _load_expense(db: Session, expense_id: int) -> Expense:
    expense = (
        db.query(Expense)
        .options(
            joinedload(Expense.splits).joinedload(ExpenseSplit.user),
            joinedload(Expense.payer),
        )
        .filter(Expense.id == expense_id)
        .first()
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


def _apply_splits(
    expense: Expense,
    amount_cents: int,
    split_type: SplitType,
    participants: list[SplitParticipantIn],
    member_ids: set[int],
) -> None:
    for p in participants:
        if p.user_id not in member_ids:
            raise HTTPException(status_code=400, detail=f"User {p.user_id} is not a group member")
    amounts = compute_split_amounts(amount_cents, split_type, participants)
    expense.splits.clear()
    for user_id, cents, shares in amounts:
        expense.splits.append(ExpenseSplit(user_id=user_id, amount_cents=cents, shares=shares))


@router.get("/groups/{group_id}/expenses", response_model=list[ExpenseOut])
def list_expenses(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ExpenseOut]:
    get_membership(db, group_id, user.id)
    expenses = (
        db.query(Expense)
        .options(
            joinedload(Expense.splits).joinedload(ExpenseSplit.user),
            joinedload(Expense.payer),
        )
        .filter(Expense.group_id == group_id)
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .all()
    )
    return [_expense_out(e) for e in expenses]


@router.post("/groups/{group_id}/expenses", response_model=ExpenseOut)
async def create_expense(
    group_id: int,
    payload: ExpenseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpenseOut:
    get_membership(db, group_id, user.id)
    group = get_group_or_404(db, group_id)
    if group.status == GroupStatus.closed:
        raise HTTPException(status_code=400, detail="Group is closed")
    member_ids = {
        m.user_id for m in db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    }
    if payload.payer_id not in member_ids:
        raise HTTPException(status_code=400, detail="Payer must be a group member")

    expense = Expense(
        group_id=group_id,
        payer_id=payload.payer_id,
        created_by_id=user.id,
        amount_cents=payload.amount_cents,
        split_type=payload.split_type,
        category=payload.category,
        expense_date=payload.expense_date,
        comment=payload.comment,
    )
    db.add(expense)
    db.flush()
    _apply_splits(expense, payload.amount_cents, payload.split_type, payload.participants, member_ids)

    involved = {payload.payer_id, *[p.user_id for p in payload.participants]}
    log_activity(
        db,
        group_id=group_id,
        actor_id=user.id,
        event_type="expense_created",
        payload={"expense_id": expense.id, "amount_cents": expense.amount_cents},
    )
    notify_users(
        db,
        user_ids=[uid for uid in involved if uid != user.id],
        notification_type="expense_created",
        payload={"group_id": group_id, "expense_id": expense.id, "amount_cents": expense.amount_cents},
    )
    db.commit()
    out = _expense_out(_load_expense(db, expense.id))
    await manager.broadcast(group_id, {"type": "balances_updated", "group_id": group_id})
    return out


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpenseOut:
    expense = _load_expense(db, expense_id)
    require_expense_mutator(
        db,
        expense.group_id,
        user,
        payer_id=expense.payer_id,
        created_by_id=expense.created_by_id,
    )
    group = get_group_or_404(db, expense.group_id)
    if group.status == GroupStatus.closed:
        raise HTTPException(status_code=400, detail="Group is closed")
    member_ids = {
        m.user_id
        for m in db.query(GroupMember).filter(GroupMember.group_id == expense.group_id).all()
    }

    if payload.payer_id is not None:
        if payload.payer_id not in member_ids:
            raise HTTPException(status_code=400, detail="Payer must be a group member")
        expense.payer_id = payload.payer_id
    if payload.amount_cents is not None:
        expense.amount_cents = payload.amount_cents
    if payload.split_type is not None:
        expense.split_type = payload.split_type
    if payload.category is not None:
        expense.category = payload.category
    if payload.expense_date is not None:
        expense.expense_date = payload.expense_date
    if payload.comment is not None:
        expense.comment = payload.comment

    if payload.participants is not None or payload.amount_cents is not None or payload.split_type is not None:
        participants = payload.participants
        if participants is None:
            participants = [
                SplitParticipantIn(user_id=s.user_id, amount_cents=s.amount_cents, shares=s.shares)
                for s in expense.splits
            ]
        _apply_splits(expense, expense.amount_cents, expense.split_type, participants, member_ids)

    involved = {expense.payer_id, *[s.user_id for s in expense.splits]}
    log_activity(
        db,
        group_id=expense.group_id,
        actor_id=user.id,
        event_type="expense_updated",
        payload={"expense_id": expense.id, "amount_cents": expense.amount_cents},
    )
    notify_users(
        db,
        user_ids=[uid for uid in involved if uid != user.id],
        notification_type="expense_updated",
        payload={
            "group_id": expense.group_id,
            "expense_id": expense.id,
            "amount_cents": expense.amount_cents,
        },
    )
    db.commit()
    out = _expense_out(_load_expense(db, expense.id))
    await manager.broadcast(expense.group_id, {"type": "balances_updated", "group_id": expense.group_id})
    return out


@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    expense = _load_expense(db, expense_id)
    require_expense_mutator(
        db,
        expense.group_id,
        user,
        payer_id=expense.payer_id,
        created_by_id=expense.created_by_id,
    )
    group = get_group_or_404(db, expense.group_id)
    if group.status == GroupStatus.closed:
        raise HTTPException(status_code=400, detail="Group is closed")
    group_id = expense.group_id
    involved = {expense.payer_id, *[s.user_id for s in expense.splits]}
    log_activity(
        db,
        group_id=group_id,
        actor_id=user.id,
        event_type="expense_deleted",
        payload={"expense_id": expense.id, "amount_cents": expense.amount_cents},
    )
    notify_users(
        db,
        user_ids=[uid for uid in involved if uid != user.id],
        notification_type="expense_deleted",
        payload={"group_id": group_id, "expense_id": expense.id},
    )
    db.delete(expense)
    db.commit()
    await manager.broadcast(group_id, {"type": "balances_updated", "group_id": group_id})
    return {"ok": True}


@router.get("/expenses/{expense_id}/receipt")
def download_receipt(
    expense_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    expense = _load_expense(db, expense_id)
    get_membership(db, expense.group_id, user.id)
    if not expense.receipt_path:
        raise HTTPException(status_code=404, detail="No receipt")
    path = Path(settings.upload_dir) / expense.receipt_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Receipt file missing")
    return FileResponse(path, filename=path.name)


@router.post("/expenses/{expense_id}/receipt", response_model=ExpenseOut)
async def upload_receipt(
    expense_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpenseOut:
    settings = get_settings()
    expense = _load_expense(db, expense_id)
    require_expense_mutator(
        db,
        expense.group_id,
        user,
        payer_id=expense.payer_id,
        created_by_id=expense.created_by_id,
    )
    suffix = Path(file.filename or "receipt.bin").suffix.lower()
    if suffix not in ALLOWED_RECEIPT_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_RECEIPT_SUFFIXES))}",
        )
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail="Receipt file too large (max 5MB)")
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    name = f"{expense_id}_{uuid.uuid4().hex}{suffix}"
    dest = upload_root / name
    dest.write_bytes(content)
    expense.receipt_path = name
    db.commit()
    return _expense_out(_load_expense(db, expense.id))
