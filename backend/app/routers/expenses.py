from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.constants import ALLOWED_RECEIPT_SUFFIXES, BYTES_PER_MEBIBYTE, EventType, WsMessageType
from app.database import get_db
from app.deps import get_current_user, get_group_or_404, get_membership, require_expense_mutator
from app.models import Expense, ExpenseSplit, ExpenseStatus, GroupMember, GroupStatus, SplitType, User
from app.schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate, SplitOut, SplitParticipantIn
from app.services.activity_service import log_activity, notify_users
from app.services.admin_action_log import log_user_action
from app.services.split_service import compute_split_amounts
from app.ws import manager

router = APIRouter(tags=["expenses"])


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
        status=expense.status,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
        payer_name=expense.payer.name if expense.payer else None,
        payer_email=expense.payer.email if expense.payer else None,
        splits=[
            SplitOut(
                user_id=s.user_id,
                amount_cents=s.amount_cents,
                shares=s.shares,
                name=s.user.name if s.user else None,
                email=s.user.email if s.user else None,
            )
            for s in expense.splits
        ],
    )


def _require_expense_open(expense: Expense) -> None:
    if expense.status == ExpenseStatus.completed:
        raise HTTPException(
            status_code=400,
            detail="Expense is completed — reopen it before editing",
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
    db: Session,
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
    # clear() alone can INSERT before DELETE in one flush → UNIQUE(expense_id, user_id)
    expense.splits.clear()
    db.flush()
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
    _apply_splits(
        db, expense, payload.amount_cents, payload.split_type, payload.participants, member_ids
    )

    involved = {payload.payer_id, *[p.user_id for p in payload.participants]}
    log_activity(
        db,
        group_id=group_id,
        actor_id=user.id,
        event_type=EventType.EXPENSE_CREATED,
        payload={"expense_id": expense.id, "amount_cents": expense.amount_cents},
    )
    notify_users(
        db,
        user_ids=[uid for uid in involved if uid != user.id],
        notification_type=EventType.EXPENSE_CREATED,
        payload={"group_id": group_id, "expense_id": expense.id, "amount_cents": expense.amount_cents},
    )
    log_user_action(
        db,
        actor=user,
        action="expense.create",
        target_type="expense",
        target_id=expense.id,
        payload={"group_id": group_id, "amount_cents": expense.amount_cents},
    )
    db.commit()
    out = _expense_out(_load_expense(db, expense.id))
    await manager.broadcast(
        group_id, {"type": WsMessageType.BALANCES_UPDATED, "group_id": group_id}
    )
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

    status_only = (
        payload.status is not None
        and payload.payer_id is None
        and payload.amount_cents is None
        and payload.split_type is None
        and payload.participants is None
        and payload.category is None
        and payload.expense_date is None
        and payload.comment is None
    )
    if not status_only:
        _require_expense_open(expense)

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

    previous_status = expense.status
    if payload.status is not None:
        expense.status = payload.status

    if payload.participants is not None or payload.amount_cents is not None or payload.split_type is not None:
        participants = payload.participants
        if participants is None:
            participants = [
                SplitParticipantIn(user_id=s.user_id, amount_cents=s.amount_cents, shares=s.shares)
                for s in expense.splits
            ]
        _apply_splits(
            db, expense, expense.amount_cents, expense.split_type, participants, member_ids
        )

    involved = {expense.payer_id, *[s.user_id for s in expense.splits]}
    if payload.status is not None and payload.status != previous_status:
        event_type = (
            EventType.EXPENSE_COMPLETED
            if payload.status == ExpenseStatus.completed
            else EventType.EXPENSE_REOPENED
        )
        admin_action = (
            "expense.complete"
            if payload.status == ExpenseStatus.completed
            else "expense.reopen"
        )
    else:
        event_type = EventType.EXPENSE_UPDATED
        admin_action = "expense.update"
    log_activity(
        db,
        group_id=expense.group_id,
        actor_id=user.id,
        event_type=event_type,
        payload={
            "expense_id": expense.id,
            "amount_cents": expense.amount_cents,
            "status": expense.status.value,
        },
    )
    notify_users(
        db,
        user_ids=[uid for uid in involved if uid != user.id],
        notification_type=event_type,
        payload={
            "group_id": expense.group_id,
            "expense_id": expense.id,
            "amount_cents": expense.amount_cents,
            "status": expense.status.value,
        },
    )
    log_user_action(
        db,
        actor=user,
        action=admin_action,
        target_type="expense",
        target_id=expense.id,
        payload={
            "group_id": expense.group_id,
            "amount_cents": expense.amount_cents,
            "status": expense.status.value,
        },
    )
    db.commit()
    out = _expense_out(_load_expense(db, expense.id))
    await manager.broadcast(
        expense.group_id,
        {"type": WsMessageType.BALANCES_UPDATED, "group_id": expense.group_id},
    )
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
    _require_expense_open(expense)
    group_id = expense.group_id
    involved = {expense.payer_id, *[s.user_id for s in expense.splits]}
    log_activity(
        db,
        group_id=group_id,
        actor_id=user.id,
        event_type=EventType.EXPENSE_DELETED,
        payload={"expense_id": expense.id, "amount_cents": expense.amount_cents},
    )
    notify_users(
        db,
        user_ids=[uid for uid in involved if uid != user.id],
        notification_type=EventType.EXPENSE_DELETED,
        payload={"group_id": group_id, "expense_id": expense.id},
    )
    log_user_action(
        db,
        actor=user,
        action="expense.delete",
        target_type="expense",
        target_id=expense.id,
        payload={"group_id": group_id, "amount_cents": expense.amount_cents},
    )
    db.delete(expense)
    db.commit()
    await manager.broadcast(
        group_id, {"type": WsMessageType.BALANCES_UPDATED, "group_id": group_id}
    )
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
    group = get_group_or_404(db, expense.group_id)
    if group.status == GroupStatus.closed:
        raise HTTPException(status_code=400, detail="Group is closed")
    _require_expense_open(expense)
    suffix = Path(file.filename or "receipt.bin").suffix.lower()
    if suffix not in ALLOWED_RECEIPT_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_RECEIPT_SUFFIXES))}",
        )
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        max_mb = max(1, settings.max_upload_bytes // BYTES_PER_MEBIBYTE)
        raise HTTPException(
            status_code=400,
            detail=f"Receipt file too large (max {max_mb}MB)",
        )
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    name = f"{expense_id}_{uuid.uuid4().hex}{suffix}"
    dest = upload_root / name
    dest.write_bytes(content)
    expense.receipt_path = name
    db.commit()
    return _expense_out(_load_expense(db, expense.id))
