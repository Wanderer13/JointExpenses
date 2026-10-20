from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import GoogleAuthIn, TokenOut, UserCreate, UserLogin, UserOut
from app.security import create_access_token, hash_password, verify_password
from app.services.google_auth import GoogleAuthError, verify_google_id_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> TokenOut:
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
    token = create_access_token(user.id)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenOut:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if (
        not user
        or user.password_hash is None
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.id)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/google", response_model=TokenOut)
def google_auth(payload: GoogleAuthIn, db: Session = Depends(get_db)) -> TokenOut:
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
    token = create_access_token(user.id)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
