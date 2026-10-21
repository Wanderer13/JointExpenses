"""Seed demo users, group, and expenses."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.bootstrap import run_migrations
from app.constants import DEFAULT_CURRENCY, DEFAULT_REMINDER_DAYS, INVITE_TOKEN_BYTES
from app.database import SessionLocal
from app.models import (
    Expense,
    ExpenseSplit,
    Group,
    GroupMember,
    GroupStatus,
    MemberRole,
    SplitType,
    User,
)
from app.security import hash_password
from app.services.roles import resolve_app_role
from app.services.split_service import compute_split_amounts
from app.schemas import SplitParticipantIn
import secrets


def main() -> None:
    run_migrations()
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == "alice@example.com").first():
            print("Seed already applied.")
            return

        alice = User(
            email="alice@example.com",
            name="Alice",
            password_hash=hash_password("password123"),
            role=resolve_app_role("alice@example.com"),
        )
        bob = User(
            email="bob@example.com",
            name="Bob",
            password_hash=hash_password("password123"),
            role=resolve_app_role("bob@example.com"),
        )
        cara = User(
            email="cara@example.com",
            name="Cara",
            password_hash=hash_password("password123"),
            role=resolve_app_role("cara@example.com"),
        )
        db.add_all([alice, bob, cara])
        db.flush()

        group = Group(
            name="Weekend Trip",
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

        # Alice paid 100.00 dinner equal split among 3
        amounts = compute_split_amounts(
            10000,
            SplitType.equal,
            [
                SplitParticipantIn(user_id=alice.id),
                SplitParticipantIn(user_id=bob.id),
                SplitParticipantIn(user_id=cara.id),
            ],
        )
        e1 = Expense(
            group_id=group.id,
            payer_id=alice.id,
            created_by_id=alice.id,
            amount_cents=10000,
            split_type=SplitType.equal,
            category="food",
            expense_date=date.today() - timedelta(days=10),
            comment="Dinner",
        )
        db.add(e1)
        db.flush()
        for uid, cents, shares in amounts:
            db.add(ExpenseSplit(expense_id=e1.id, user_id=uid, amount_cents=cents, shares=shares))

        # Bob paid 45.00 taxi exact
        e2 = Expense(
            group_id=group.id,
            payer_id=bob.id,
            created_by_id=bob.id,
            amount_cents=4500,
            split_type=SplitType.exact,
            category="transport",
            expense_date=date.today() - timedelta(days=9),
            comment="Taxi",
        )
        db.add(e2)
        db.flush()
        db.add(ExpenseSplit(expense_id=e2.id, user_id=alice.id, amount_cents=1500))
        db.add(ExpenseSplit(expense_id=e2.id, user_id=bob.id, amount_cents=1500))
        db.add(ExpenseSplit(expense_id=e2.id, user_id=cara.id, amount_cents=1500))

        db.commit()
        print("Seed OK.")
        print("Users: alice@example.com / bob@example.com / cara@example.com")
        print("Password: password123")
        print(f"Group invite token: {group.invite_token}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
