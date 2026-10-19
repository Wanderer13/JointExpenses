from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_group_or_404, get_membership
from app.models import User
from app.schemas import GroupBalancesOut, MyBalanceItemOut
from app.services.balance_service import group_balances_payload, user_balances_across_groups

router = APIRouter(tags=["balances"])


@router.get("/groups/{group_id}/balances", response_model=GroupBalancesOut)
def group_balances(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupBalancesOut:
    get_membership(db, group_id, user.id)
    group = get_group_or_404(db, group_id)
    return GroupBalancesOut(**group_balances_payload(db, group))


@router.get("/balances/me", response_model=list[MyBalanceItemOut])
def my_balances(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MyBalanceItemOut]:
    return [MyBalanceItemOut(**item) for item in user_balances_across_groups(db, user.id)]
