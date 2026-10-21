from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants import (
    DEFAULT_CATEGORY,
    DEFAULT_CURRENCY,
    DEFAULT_REMINDER_DAYS,
    MAX_PASSWORD_LENGTH,
    MAX_REMINDER_DAYS,
    MIN_PASSWORD_LENGTH,
    MIN_REMINDER_DAYS,
)
from app.currencies import is_allowed_currency, normalize_currency
from app.models import AppRole, ExpenseStatus, GroupStatus, MemberRole, SettlementStatus, SplitType


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthIn(BaseModel):
    credential: str = Field(min_length=1)
    password: str | None = Field(
        default=None, min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    role: AppRole = AppRole.user


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    role: AppRole
    has_password: bool
    google_linked: bool


class AdminRoleUpdate(BaseModel):
    role: AppRole


class ClearLinkedUsersOut(BaseModel):
    deleted_user_ids: list[int]
    deleted_count: int


class AdminActionLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    actor_email: str | None
    action: str
    target_type: str | None
    target_id: int | None
    payload: dict
    created_at: datetime


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=8)
    reminder_days: int = Field(
        default=DEFAULT_REMINDER_DAYS, ge=MIN_REMINDER_DAYS, le=MAX_REMINDER_DAYS
    )

    @field_validator("currency")
    @classmethod
    def currency_must_be_allowed(cls, value: str) -> str:
        code = normalize_currency(value)
        if not is_allowed_currency(code):
            raise ValueError(f"Unsupported currency: {code}")
        return code


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    reminder_days: int | None = Field(
        default=None, ge=MIN_REMINDER_DAYS, le=MAX_REMINDER_DAYS
    )

    @field_validator("currency")
    @classmethod
    def currency_must_be_allowed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = normalize_currency(value)
        if not is_allowed_currency(code):
            raise ValueError(f"Unsupported currency: {code}")
        return code


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    role: MemberRole
    name: str
    email: EmailStr
    awaiting_signup: bool = False


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


class InviteEmailOut(BaseModel):
    message: str
    join_url: str


class JoinPreviewOut(BaseModel):
    name: str
    status: GroupStatus
    currency: str


class SplitParticipantIn(BaseModel):
    user_id: int
    amount_cents: int | None = None
    shares: int | None = Field(default=None, ge=1)


class ExpenseCreate(BaseModel):
    payer_id: int
    amount_cents: int = Field(gt=0)
    split_type: SplitType
    participants: list[SplitParticipantIn] = Field(min_length=1)
    category: str = DEFAULT_CATEGORY
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
    status: ExpenseStatus | None = None


class SplitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    amount_cents: int
    shares: int | None = None
    name: str | None = None
    email: EmailStr | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    payer_id: int
    created_by_id: int
    amount_cents: int
    split_type: SplitType
    category: str
    expense_date: date
    comment: str | None
    receipt_path: str | None
    status: ExpenseStatus
    created_at: datetime
    updated_at: datetime
    splits: list[SplitOut] = []
    payer_name: str | None = None
    payer_email: EmailStr | None = None


class NetBalanceOut(BaseModel):
    user_id: int
    name: str
    email: EmailStr | None = None
    balance_cents: int


class TransferSuggestionOut(BaseModel):
    from_user_id: int
    from_name: str
    from_email: EmailStr | None = None
    to_user_id: int
    to_name: str
    to_email: EmailStr | None = None
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
    # When true, confirm in the same request (payer declaring paid, or other party still invited).
    confirm_now: bool = False


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
    from_email: EmailStr | None = None
    to_name: str | None = None
    to_email: EmailStr | None = None


class PendingSettlementOut(BaseModel):
    id: int
    group_id: int
    group_name: str
    currency: str
    from_user_id: int
    to_user_id: int
    amount_cents: int
    status: SettlementStatus
    created_at: datetime
    from_name: str
    from_email: EmailStr
    to_name: str
    to_email: EmailStr
    counterpart_user_id: int
    counterpart_name: str
    counterpart_email: EmailStr
    needs_my_action: bool = True


class CurrencyBalanceSummaryOut(BaseModel):
    currency: str
    you_owe_cents: int
    owed_to_you_cents: int


class OpenExpenseOut(BaseModel):
    id: int
    group_id: int
    group_name: str
    currency: str
    category: str
    amount_cents: int
    expense_date: date
    payer_id: int
    payer_name: str
    payer_email: EmailStr


class OverviewOut(BaseModel):
    pending_settlements: list[PendingSettlementOut]
    balances_by_currency: list[CurrencyBalanceSummaryOut]
    group_balances: list[MyBalanceItemOut]
    open_expenses: list[OpenExpenseOut]
    pending_settlement_count: int


class SharedGroupOut(BaseModel):
    id: int
    name: str
    currency: str
    status: GroupStatus


class UserProfileOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    shared_groups: list[SharedGroupOut] = []


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
