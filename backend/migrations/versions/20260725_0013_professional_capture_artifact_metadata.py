"""Add Professional Intelligence capture artifact metadata.

Revision ID: 20260725_0013
Revises: 20260725_0012
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260725_0013"
down_revision = "20260725_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "professional_capture_artifacts",
        sa.Column("completeness_status", sa.String(length=20), nullable=False, server_default="partial"),
    )
    op.add_column(
        "professional_capture_artifacts",
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    op.drop_column("professional_capture_artifacts", "retention_days")
    op.drop_column("professional_capture_artifacts", "completeness_status")
