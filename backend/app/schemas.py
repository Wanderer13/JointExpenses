from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import GroupStatus, MemberRole, SettlementStatus, SplitType


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthIn(BaseModel):
    credential: str = Field(min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    reminder_days: int = Field(default=7, ge=1, le=365)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    reminder_days: int | None = Field(default=None, ge=1, le=365)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    role: MemberRole
    name: str
    email: EmailStr


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    currency: str
    reminder_days: int
    status: GroupStatus
    invite_token: str
    created_at: datetime
    members: list[MemberOut] = []


class InviteEmailIn(BaseModel):
    email: EmailStr


class SplitParticipantIn(BaseModel):
    user_id: int
    amount_cents: int | None = None
    shares: int | None = Field(default=None, ge=1)


class ExpenseCreate(BaseModel):
    payer_id: int
    amount_cents: int = Field(gt=0)
    split_type: SplitType
    participants: list[SplitParticipantIn] = Field(min_length=1)
    category: str = "general"
    expense_date: date
    comment: str | None = None


class ExpenseUpdate(BaseModel):
    payer_id: int | None = None
    amount_cents: int | None = Field(default=None, gt=0)
    split_type: SplitType | None = None
    participants: list[SplitParticipantIn] | None = None
    category: str | None = None
    expense_date: date | None = None
    comment: str | None = None


class SplitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    amount_cents: int
    shares: int | None = None
    name: str | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    payer_id: int
    amount_cents: int
    split_type: SplitType
    category: str
    expense_date: date
    comment: str | None
    receipt_path: str | None
    created_at: datetime
    updated_at: datetime
    splits: list[SplitOut] = []
    payer_name: str | None = None


class NetBalanceOut(BaseModel):
    user_id: int
    name: str
    balance_cents: int


class TransferSuggestionOut(BaseModel):
    from_user_id: int
    from_name: str
    to_user_id: int
    to_name: str
    amount_cents: int


class GroupBalancesOut(BaseModel):
    group_id: int
    currency: str
    nets: list[NetBalanceOut]
    suggested_transfers: list[TransferSuggestionOut]
    sum_check: int


class MyBalanceItemOut(BaseModel):
    group_id: int
    group_name: str
    currency: str
    balance_cents: int


class SettlementCreate(BaseModel):
    from_user_id: int
    to_user_id: int
    amount_cents: int = Field(gt=0)


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    from_user_id: int
    to_user_id: int
    amount_cents: int
    status: SettlementStatus
    created_at: datetime
    confirmed_at: datetime | None
    from_name: str | None = None
    to_name: str | None = None


class ActivityOut(BaseModel):
    id: int
    group_id: int
    actor_id: int | None
    actor_name: str | None
    event_type: str
    payload: dict
    created_at: datetime


class NotificationOut(BaseModel):
    id: int
    notification_type: str
    payload: dict
    read_at: datetime | None
    created_at: datetime


class MessageOut(BaseModel):
    message: str


class SettlementAction(BaseModel):
    action: Literal["confirm", "reject"]
