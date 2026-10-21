from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.constants import ACCESS_COOKIE
from app.database import get_db
from app.models import AppRole, Group, GroupMember, MemberRole, User
from app.security import decode_token, get_user_by_id

bearer = HTTPBearer(auto_error=False)


def _extract_token(
    request: Request,
    creds: HTTPAuthorizationCredentials | None,
) -> str | None:
    if creds is not None:
        return creds.credentials
    return request.cookies.get(ACCESS_COOKIE)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_token(request, creds)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != AppRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


def get_membership(db: Session, group_id: int, user_id: int) -> GroupMember:
    membership = (
        db.query(GroupMember)
        .filter(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a group member")
    return membership


def get_group_or_404(db: Session, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def require_expense_mutator(db: Session, group_id: int, user: User, *, payer_id: int, created_by_id: int) -> None:
    membership = get_membership(db, group_id, user.id)
    if user.id in (payer_id, created_by_id) or membership.role == MemberRole.owner:
        return
    raise HTTPException(status_code=403, detail="Only payer, creator, or owner can modify this expense")
