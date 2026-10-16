"""Preserve verified portal capture occurrences after raw capture retention.

Revision ID: 20261016_0033
Revises: 20261016_0032
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261016_0033"
down_revision = "20261016_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_source_observations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("portal", sa.String(length=40), nullable=False),
        sa.Column("source_job_id", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("posting_id_at_capture", sa.String(length=36), nullable=False),
        sa.Column("capture_run_id", sa.String(length=36), nullable=False),
        sa.Column("capture_item_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id_at_capture", sa.String(length=36), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("portal", "capture_item_id", name="uq_portal_source_observation_item"),
    )
    op.create_index(
        "ix_portal_source_observations_portal", "portal_source_observations", ["portal"]
    )
    op.create_index(
        "ix_portal_source_observations_posting_id_at_capture",
        "portal_source_observations",
        ["posting_id_at_capture"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portal_source_observations_posting_id_at_capture",
        table_name="portal_source_observations",
    )
    op.drop_index("ix_portal_source_observations_portal", table_name="portal_source_observations")
    op.drop_table("portal_source_observations")
