"""Add Professional Intelligence source overrides.

Revision ID: 20260724_0009
Revises: 20260724_0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260724_0009"
down_revision = "20260724_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "professional_source_overrides",
        sa.Column("source_id", sa.Text(), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("initial_scope", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("professional_source_overrides")
