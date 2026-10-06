"""Add persistent discovery execution records.

Revision ID: 20261006_0028
Revises: 20261005_0027
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261006_0028"
down_revision = "20261005_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_executions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("saved_search_id", sa.String(length=36), nullable=False),
        sa.Column("label_snapshot", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("capture_run_id", sa.String(length=36), nullable=True),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_discovery_executions_source",
        "discovery_executions",
        ["source"],
        unique=False,
    )
    op.create_index(
        "ix_discovery_executions_saved_search_id",
        "discovery_executions",
        ["saved_search_id"],
        unique=False,
    )
    op.create_index(
        "ix_discovery_executions_status",
        "discovery_executions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_discovery_executions_status", table_name="discovery_executions")
    op.drop_index("ix_discovery_executions_saved_search_id", table_name="discovery_executions")
    op.drop_index("ix_discovery_executions_source", table_name="discovery_executions")
    op.drop_table("discovery_executions")
