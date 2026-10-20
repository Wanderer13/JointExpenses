"""Shared application constants (no magic numbers/strings in call sites)."""

from __future__ import annotations

# Money
CENTS_PER_UNIT = 100

# Time
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR
DAYS_PER_WEEK = 7
MINUTES_PER_HOUR = 60

# Defaults
DEFAULT_CURRENCY = "USD"
DEFAULT_CATEGORY = "general"
DEFAULT_REMINDER_DAYS = 7
MIN_REMINDER_DAYS = 1
MAX_REMINDER_DAYS = 365
DEFAULT_APP_ENV = "development"
APP_ENV_PRODUCTION = "production"
DEFAULT_SECRET = "dev-secret-change-me"

# Auth / tokens
TOKEN_TYPE_ACCESS = "access"
ACCESS_COOKIE = "se_access"
REFRESH_COOKIE = "se_refresh"
JWT_ALGORITHM = "HS256"
INVITE_TOKEN_BYTES = 24
REFRESH_TOKEN_BYTES = 48
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 7
AUTH_RATE_WINDOW_SECONDS = 60.0
DEFAULT_AUTH_RATE_LIMIT_PER_MINUTE = 30

# Google account linking (must match auth router detail text)
GOOGLE_LINK_PASSWORD_REQUIRED = "Account exists — provide password to link Google Sign-In"

# Mail
MAIL_BACKEND_STUB = "stub"
MAIL_BACKEND_SMTP = "smtp"
DEFAULT_SMTP_PORT = 587

# Uploads
BYTES_PER_KIBIBYTE = 1024
BYTES_PER_MEBIBYTE = BYTES_PER_KIBIBYTE * BYTES_PER_KIBIBYTE
DEFAULT_MAX_UPLOAD_MEBIBYTES = 5
DEFAULT_MAX_UPLOAD_BYTES = DEFAULT_MAX_UPLOAD_MEBIBYTES * BYTES_PER_MEBIBYTE
ALLOWED_RECEIPT_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".pdf"})

# API list limits
FEED_PAGE_LIMIT = 100

# WebSocket close codes (application-defined)
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403

# Scheduler
DEFAULT_REMINDER_CHECK_SECONDS = 60


class EventType:
    GROUP_CREATED = "group_created"
    GROUP_CLOSED = "group_closed"
    GROUP_REOPENED = "group_reopened"
    MEMBER_JOINED = "member_joined"
    INVITE_SENT = "invite_sent"
    EXPENSE_CREATED = "expense_created"
    EXPENSE_UPDATED = "expense_updated"
    EXPENSE_DELETED = "expense_deleted"
    SETTLEMENT_PENDING = "settlement_pending"
    SETTLEMENT_CONFIRMED = "settlement_confirmed"
    SETTLEMENT_REJECTED = "settlement_rejected"


class WsMessageType:
    BALANCES_UPDATED = "balances_updated"
    GROUP_UPDATED = "group_updated"
    SETTLEMENT_UPDATED = "settlement_updated"


def cents_to_major(cents: int) -> float:
    return cents / CENTS_PER_UNIT


def format_money_major(cents: int) -> str:
    return f"{cents_to_major(cents):.2f}"
