"""Add capture run evidence tables.

Revision ID: 20260712_0003
Revises: 20260712_0002
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260712_0003"
down_revision: str | None = "20260712_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capture_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("search_url", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capture_runs_source", "capture_runs", ["source"])

    op.create_table(
        "capture_pages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_run_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("visible_job_ids_json", sa.Text(), nullable=False),
        sa.Column("next_control_present", sa.Boolean(), nullable=False),
        sa.Column("next_control_enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["capture_run_id"], ["capture_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capture_pages_capture_run_id", "capture_pages", ["capture_run_id"])

    op.create_table(
        "capture_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_job_id", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("detail_status", sa.String(length=40), nullable=False),
        sa.Column("verification_reasons_json", sa.Text(), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("posting_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["capture_run_id"], ["capture_runs.id"]),
        sa.ForeignKeyConstraint(["posting_id"], ["postings.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capture_items_capture_run_id", "capture_items", ["capture_run_id"])
    op.create_index("ix_capture_items_source_job_id", "capture_items", ["source_job_id"])
    op.create_index("ix_capture_items_source_document_id", "capture_items", ["source_document_id"])
    op.create_index("ix_capture_items_posting_id", "capture_items", ["posting_id"])


def downgrade() -> None:
    op.drop_index("ix_capture_items_posting_id", table_name="capture_items")
    op.drop_index("ix_capture_items_source_document_id", table_name="capture_items")
    op.drop_index("ix_capture_items_source_job_id", table_name="capture_items")
    op.drop_index("ix_capture_items_capture_run_id", table_name="capture_items")
    op.drop_table("capture_items")
    op.drop_index("ix_capture_pages_capture_run_id", table_name="capture_pages")
    op.drop_table("capture_pages")
    op.drop_index("ix_capture_runs_source", table_name="capture_runs")
    op.drop_table("capture_runs")
