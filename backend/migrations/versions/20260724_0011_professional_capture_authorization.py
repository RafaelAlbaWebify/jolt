"""Add Professional Intelligence capture authorization.

Revision ID: 20260724_0011
Revises: 20260724_0010
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260724_0011"
down_revision = "20260724_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "professional_capture_runs",
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "professional_capture_runs",
        sa.Column("authorization_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "professional_capture_runs",
        sa.Column("user_present_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("professional_capture_runs", "user_present_confirmed")
    op.drop_column("professional_capture_runs", "authorization_expires_at")
    op.drop_column("professional_capture_runs", "authorized_at")
