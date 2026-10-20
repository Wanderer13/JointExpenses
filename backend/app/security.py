from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import RefreshToken, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_COOKIE = "se_access"
REFRESH_COOKIE = "se_refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire, "type": "access"}, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") not in (None, "access"):
            return None
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except (JWTError, ValueError, TypeError):
        return None


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_refresh_token(db: Session, user_id: int) -> str:
    settings = get_settings()
    raw = secrets.token_urlsafe(48)
    token = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(token)
    db.commit()
    return raw


def revoke_refresh_token(db: Session, raw: str | None) -> None:
    if not raw:
        return
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_refresh_token(raw)).first()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()


def rotate_refresh_token(db: Session, raw: str) -> tuple[User, str] | None:
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_refresh_token(raw)).first()
    if row is None or row.revoked_at is not None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    user = db.get(User, row.user_id)
    if user is None:
        return None
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    new_raw = issue_refresh_token(db, user.id)
    return user, new_raw


def cookie_kwargs() -> dict:
    settings = get_settings()
    return {
        "httponly": True,
        "secure": settings.cookie_secure or settings.is_production,
        "samesite": "lax",
        "path": "/",
    }
