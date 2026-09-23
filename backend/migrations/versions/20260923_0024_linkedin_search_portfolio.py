"""Add saved LinkedIn searches and discovery batch ledger.

Revision ID: 20260923_0024
Revises: 20260919_0023
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260923_0024"
down_revision = "20260919_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linkedin_saved_searches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("search_url", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_jobs", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("max_pages", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("search_url", name="uq_linkedin_saved_searches_search_url"),
    )
    op.create_index(
        "ix_linkedin_saved_searches_enabled",
        "linkedin_saved_searches",
        ["enabled"],
    )

    op.create_table(
        "linkedin_discovery_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("selected_search_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_linkedin_discovery_batches_status",
        "linkedin_discovery_batches",
        ["status"],
    )

    op.create_table(
        "linkedin_discovery_batch_searches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("linkedin_discovery_batches.id"),
            nullable=False,
        ),
        sa.Column(
            "saved_search_id",
            sa.String(length=36),
            sa.ForeignKey("linkedin_saved_searches.id"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label_snapshot", sa.Text(), nullable=False),
        sa.Column("search_url_snapshot", sa.Text(), nullable=False),
        sa.Column("max_jobs_snapshot", sa.Integer(), nullable=False),
        sa.Column("max_pages_snapshot", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "capture_run_id",
            sa.String(length=36),
            sa.ForeignKey("capture_runs.id"),
            nullable=True,
        ),
        sa.Column("captured_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_posting_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "batch_id",
            "position",
            name="uq_linkedin_discovery_batch_search_position",
        ),
    )
    op.create_index(
        "ix_linkedin_discovery_batch_searches_batch_id",
        "linkedin_discovery_batch_searches",
        ["batch_id"],
    )
    op.create_index(
        "ix_linkedin_discovery_batch_searches_saved_search_id",
        "linkedin_discovery_batch_searches",
        ["saved_search_id"],
    )
    op.create_index(
        "ix_linkedin_discovery_batch_searches_capture_run_id",
        "linkedin_discovery_batch_searches",
        ["capture_run_id"],
    )
    op.create_index(
        "ix_linkedin_discovery_batch_searches_status",
        "linkedin_discovery_batch_searches",
        ["status"],
    )


def downgrade() -> None:
    op.drop_table("linkedin_discovery_batch_searches")
    op.drop_table("linkedin_discovery_batches")
    op.drop_table("linkedin_saved_searches")
