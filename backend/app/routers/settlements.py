from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, get_group_or_404, get_membership
from app.models import GroupMember, GroupStatus, Settlement, SettlementStatus, User
from app.schemas import SettlementAction, SettlementCreate, SettlementOut
from app.services.activity_service import log_activity, notify_users
from app.ws import manager

router = APIRouter(tags=["settlements"])


def _settlement_out(s: Settlement) -> SettlementOut:
    return SettlementOut(
        id=s.id,
        group_id=s.group_id,
        from_user_id=s.from_user_id,
        to_user_id=s.to_user_id,
        amount_cents=s.amount_cents,
        status=s.status,
        created_at=s.created_at,
        confirmed_at=s.confirmed_at,
        from_name=s.from_user.name if s.from_user else None,
        to_name=s.to_user.name if s.to_user else None,
    )


def _load(db: Session, settlement_id: int) -> Settlement:
    s = (
        db.query(Settlement)
        .options(joinedload(Settlement.from_user), joinedload(Settlement.to_user))
        .filter(Settlement.id == settlement_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Settlement not found")
    return s


@router.get("/groups/{group_id}/settlements", response_model=list[SettlementOut])
def list_settlements(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SettlementOut]:
    get_membership(db, group_id, user.id)
    rows = (
        db.query(Settlement)
        .options(joinedload(Settlement.from_user), joinedload(Settlement.to_user))
        .filter(Settlement.group_id == group_id)
        .order_by(Settlement.created_at.desc())
        .all()
    )
    return [_settlement_out(s) for s in rows]


@router.post("/groups/{group_id}/settlements", response_model=SettlementOut)
async def create_settlement(
    group_id: int,
    payload: SettlementCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettlementOut:
    get_membership(db, group_id, user.id)
    group = get_group_or_404(db, group_id)
    if group.status == GroupStatus.closed:
        raise HTTPException(status_code=400, detail="Group is closed")
    member_ids = {
        m.user_id for m in db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    }
    if payload.from_user_id not in member_ids or payload.to_user_id not in member_ids:
        raise HTTPException(status_code=400, detail="Both users must be members")
    if payload.from_user_id == payload.to_user_id:
        raise HTTPException(status_code=400, detail="Cannot settle with yourself")
    if user.id not in (payload.from_user_id, payload.to_user_id):
        raise HTTPException(status_code=403, detail="You must be a party to the settlement")

    settlement = Settlement(
        group_id=group_id,
        from_user_id=payload.from_user_id,
        to_user_id=payload.to_user_id,
        amount_cents=payload.amount_cents,
        status=SettlementStatus.pending,
    )
    db.add(settlement)
    db.flush()
    log_activity(
        db,
        group_id=group_id,
        actor_id=user.id,
        event_type="settlement_pending",
        payload={
            "settlement_id": settlement.id,
            "from_user_id": payload.from_user_id,
            "to_user_id": payload.to_user_id,
            "amount_cents": payload.amount_cents,
        },
    )
    other = payload.to_user_id if user.id == payload.from_user_id else payload.from_user_id
    notify_users(
        db,
        user_ids=[other],
        notification_type="settlement_pending",
        payload={"group_id": group_id, "settlement_id": settlement.id},
    )
    db.commit()
    out = _settlement_out(_load(db, settlement.id))
    await manager.broadcast(group_id, {"type": "settlement_updated", "group_id": group_id})
    return out


@router.post("/settlements/{settlement_id}/action", response_model=SettlementOut)
async def settlement_action(
    settlement_id: int,
    payload: SettlementAction,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettlementOut:
    settlement = _load(db, settlement_id)
    get_membership(db, settlement.group_id, user.id)
    if settlement.status != SettlementStatus.pending:
        raise HTTPException(status_code=400, detail="Settlement is not pending")
    if user.id != settlement.to_user_id:
        raise HTTPException(status_code=403, detail="Only recipient can confirm or reject")

    if payload.action == "confirm":
        settlement.status = SettlementStatus.confirmed
        settlement.confirmed_at = datetime.now(timezone.utc)
        event_type = "settlement_confirmed"
    else:
        settlement.status = SettlementStatus.rejected
        event_type = "settlement_rejected"

    log_activity(
        db,
        group_id=settlement.group_id,
        actor_id=user.id,
        event_type=event_type,
        payload={"settlement_id": settlement.id, "amount_cents": settlement.amount_cents},
    )
    notify_users(
        db,
        user_ids=[settlement.from_user_id],
        notification_type=event_type,
        payload={"group_id": settlement.group_id, "settlement_id": settlement.id},
    )
    db.commit()
    out = _settlement_out(_load(db, settlement.id))
    await manager.broadcast(
        settlement.group_id,
        {"type": "balances_updated", "group_id": settlement.group_id},
    )
    return out
