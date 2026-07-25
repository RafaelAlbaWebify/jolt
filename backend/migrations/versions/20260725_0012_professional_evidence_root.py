"""Add Professional Intelligence local evidence root.

Revision ID: 20260725_0012
Revises: 20260724_0011
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260725_0012"
down_revision = "20260724_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "professional_evidence_settings",
        sa.Column("id", sa.String(length=24), primary_key=True),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("professional_evidence_settings")
