"""Expense status open/completed

Revision ID: 004_expense_status
Revises: 003_user_app_role
Create Date: 2026-10-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_expense_status"
down_revision: Union[str, None] = "003_user_app_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
    )


def downgrade() -> None:
    op.drop_column("expenses", "status")
