"""Add durable LinkedIn discovery batch review set.

Revision ID: 20260923_0025
Revises: 20260923_0024
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260923_0025"
down_revision = "20260923_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linkedin_discovery_batch_review_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("linkedin_discovery_batches.id"),
            nullable=False,
        ),
        sa.Column(
            "posting_id",
            sa.String(length=36),
            sa.ForeignKey("postings.id"),
            nullable=False,
        ),
        sa.Column(
            "representative_capture_run_id",
            sa.String(length=36),
            sa.ForeignKey("capture_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "representative_capture_item_id",
            sa.String(length=36),
            sa.ForeignKey("capture_items.id"),
            nullable=False,
        ),
        sa.Column("representative_source_job_id", sa.String(length=100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "batch_id",
            "posting_id",
            name="uq_linkedin_discovery_batch_review_posting",
        ),
        sa.UniqueConstraint(
            "batch_id",
            "position",
            name="uq_linkedin_discovery_batch_review_position",
        ),
    )
    op.create_index(
        "ix_linkedin_discovery_batch_review_items_batch_id",
        "linkedin_discovery_batch_review_items",
        ["batch_id"],
    )
    op.create_index(
        "ix_linkedin_discovery_batch_review_items_posting_id",
        "linkedin_discovery_batch_review_items",
        ["posting_id"],
    )


def downgrade() -> None:
    op.drop_table("linkedin_discovery_batch_review_items")
