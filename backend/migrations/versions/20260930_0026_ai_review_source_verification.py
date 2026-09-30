"""Add official-source work-model verification to AI reviews.

Revision ID: 20260930_0026
Revises: 20260923_0025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260930_0026"
down_revision = "20260923_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ai_reviews") as batch:
        batch.add_column(
            sa.Column("source_conflict", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column(
                "linkedin_work_model",
                sa.String(length=24),
                nullable=False,
                server_default="unknown",
            )
        )
        batch.add_column(
            sa.Column(
                "official_work_model",
                sa.String(length=24),
                nullable=False,
                server_default="unknown",
            )
        )
        batch.add_column(
            sa.Column(
                "authoritative_source",
                sa.String(length=32),
                nullable=False,
                server_default="unknown",
            )
        )
        batch.add_column(
            sa.Column("official_source_url", sa.Text(), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "remote_status",
                sa.String(length=32),
                nullable=False,
                server_default="unknown",
            )
        )
        batch.add_column(
            sa.Column(
                "location_verification_status",
                sa.String(length=32),
                nullable=False,
                server_default="unverified",
            )
        )
        batch.add_column(
            sa.Column(
                "source_confidence",
                sa.String(length=20),
                nullable=False,
                server_default="unknown",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_reviews") as batch:
        batch.drop_column("source_confidence")
        batch.drop_column("location_verification_status")
        batch.drop_column("remote_status")
        batch.drop_column("official_source_url")
        batch.drop_column("authoritative_source")
        batch.drop_column("official_work_model")
        batch.drop_column("linkedin_work_model")
        batch.drop_column("source_conflict")
