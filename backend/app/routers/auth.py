from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import (
    ACCESS_COOKIE,
    GOOGLE_LINK_PASSWORD_REQUIRED,
    REFRESH_COOKIE,
    SECONDS_PER_DAY,
    SECONDS_PER_MINUTE,
)
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.rate_limit import check_auth_rate_limit
from app.schemas import GoogleAuthIn, MessageOut, TokenOut, UserCreate, UserLogin, UserOut
from app.security import (
    cookie_kwargs,
    create_access_token,
    hash_password,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from app.services.google_auth import GoogleAuthError, verify_google_id_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    settings = get_settings()
    kwargs = cookie_kwargs()
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=settings.access_token_expire_minutes * SECONDS_PER_MINUTE,
        **kwargs,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.refresh_token_expire_days * SECONDS_PER_DAY,
        **kwargs,
    )


def _clear_auth_cookies(response: Response) -> None:
    kwargs = cookie_kwargs()
    response.delete_cookie(ACCESS_COOKIE, path=kwargs["path"])
    response.delete_cookie(REFRESH_COOKIE, path=kwargs["path"])


def _issue_tokens(response: Response, db: Session, user: User) -> TokenOut:
    access = create_access_token(user.id)
    refresh = issue_refresh_token(db, user.id)
    _set_auth_cookies(response, access, refresh)
    return TokenOut(access_token=access, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut)
def register(
    payload: UserCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenOut:
    check_auth_rate_limit(request)
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email.lower(),
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(response, db, user)


@router.post("/login", response_model=TokenOut)
def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenOut:
    check_auth_rate_limit(request)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if (
        not user
        or user.password_hash is None
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return _issue_tokens(response, db, user)


@router.post("/google", response_model=TokenOut)
def google_auth(
    payload: GoogleAuthIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenOut:
    check_auth_rate_limit(request)
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sign-In is not configured",
        )
    try:
        idinfo = verify_google_id_token(payload.credential, settings.google_client_id)
    except GoogleAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    google_sub = str(idinfo["sub"])
    email = str(idinfo["email"]).lower()
    name = str(idinfo.get("name") or email.split("@")[0])[:120]

    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user is None:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            if not payload.password:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=GOOGLE_LINK_PASSWORD_REQUIRED,
                )
            if user.password_hash is None or not verify_password(payload.password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid password for account linking",
                )
            user.google_sub = google_sub
            if not user.name.strip():
                user.name = name
        else:
            user = User(
                email=email,
                name=name,
                password_hash=None,
                google_sub=google_sub,
            )
            db.add(user)

    db.commit()
    db.refresh(user)
    return _issue_tokens(response, db, user)


@router.post("/refresh", response_model=TokenOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    rotated = rotate_refresh_token(db, raw)
    if rotated is None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user, new_refresh = rotated
    access = create_access_token(user.id)
    _set_auth_cookies(response, access, new_refresh)
    return TokenOut(access_token=access, user=UserOut.model_validate(user))


@router.post("/logout", response_model=MessageOut)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> MessageOut:
    revoke_refresh_token(db, request.cookies.get(REFRESH_COOKIE))
    _clear_auth_cookies(response)
    return MessageOut(message="Logged out")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
