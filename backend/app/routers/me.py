"""Current-user overview and co-member profiles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import OverviewOut, UserProfileOut
from app.services.overview_service import build_overview, build_user_profile

router = APIRouter(tags=["me"])


@router.get("/me/overview", response_model=OverviewOut)
def my_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OverviewOut:
    return OverviewOut(**build_overview(db, user))


@router.get("/users/{user_id}", response_model=UserProfileOut)
def user_profile(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileOut:
    profile = build_user_profile(db, user, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfileOut(**profile)
