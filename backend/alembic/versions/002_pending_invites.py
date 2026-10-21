"""Pending email invites

Revision ID: 002_pending_invites
Revises: 001_initial
Create Date: 2026-10-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_pending_invites"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "email", name="uq_pending_invite_group_email"),
    )
    op.create_index("ix_pending_invites_group_id", "pending_invites", ["group_id"])
    op.create_index("ix_pending_invites_email", "pending_invites", ["email"])


def downgrade() -> None:
    op.drop_index("ix_pending_invites_email", table_name="pending_invites")
    op.drop_index("ix_pending_invites_group_id", table_name="pending_invites")
    op.drop_table("pending_invites")
