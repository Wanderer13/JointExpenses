from __future__ import annotations

import secrets
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.constants import DEFAULT_CURRENCY, DEFAULT_REMINDER_DAYS, INVITE_TOKEN_BYTES
from app.database import Base, get_db
from app.main import app
from app.models import Group, GroupMember, GroupStatus, MemberRole, User
from app.rate_limit import _buckets
from app.security import hash_password


@pytest.fixture(autouse=True)
def _clear_auth_rate_limits():
    _buckets.clear()
    yield
    _buckets.clear()


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture()
def db(engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine) -> Generator[TestClient, None, None]:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def users(db: Session) -> list[User]:
    alice = User(email="alice@test.com", name="Alice", password_hash=hash_password("password123"))
    bob = User(email="bob@test.com", name="Bob", password_hash=hash_password("password123"))
    cara = User(email="cara@test.com", name="Cara", password_hash=hash_password("password123"))
    db.add_all([alice, bob, cara])
    db.commit()
    for u in (alice, bob, cara):
        db.refresh(u)
    return [alice, bob, cara]


@pytest.fixture()
def group_with_members(db: Session, users: list[User]) -> Group:
    alice, bob, cara = users
    group = Group(
        name="Trip",
        currency=DEFAULT_CURRENCY,
        reminder_days=DEFAULT_REMINDER_DAYS,
        status=GroupStatus.open,
        invite_token=secrets.token_urlsafe(INVITE_TOKEN_BYTES),
        created_by_id=alice.id,
    )
    db.add(group)
    db.flush()
    db.add_all(
        [
            GroupMember(group_id=group.id, user_id=alice.id, role=MemberRole.owner),
            GroupMember(group_id=group.id, user_id=bob.id, role=MemberRole.member),
            GroupMember(group_id=group.id, user_id=cara.id, role=MemberRole.member),
        ]
    )
    db.commit()
    db.refresh(group)
    return group
