"""Add Professional Intelligence capture run ledger.

Revision ID: 20260724_0010
Revises: 20260724_0009
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260724_0010"
down_revision = "20260724_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "professional_capture_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source_snapshot_json", sa.Text(), nullable=False),
        sa.Column("safety_constraints_json", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_reason", sa.String(length=80), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_professional_capture_runs_requested_at",
        "professional_capture_runs",
        ["requested_at"],
    )

    op.create_table(
        "professional_capture_artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("capture_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["capture_run_id"], ["professional_capture_runs.id"]),
    )
    op.create_index(
        "ix_professional_capture_artifacts_capture_run_id",
        "professional_capture_artifacts",
        ["capture_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_professional_capture_artifacts_capture_run_id",
        table_name="professional_capture_artifacts",
    )
    op.drop_table("professional_capture_artifacts")
    op.drop_index(
        "ix_professional_capture_runs_requested_at",
        table_name="professional_capture_runs",
    )
    op.drop_table("professional_capture_runs")
