"""App-level role helpers (admin vs user)."""

from __future__ import annotations

from app.config import get_settings
from app.models import AppRole


def resolve_app_role(email: str) -> AppRole:
    if email.lower() in get_settings().admin_email_set:
        return AppRole.admin
    return AppRole.user
