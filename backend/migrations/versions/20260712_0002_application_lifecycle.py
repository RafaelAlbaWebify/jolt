"""Add application lifecycle and outcomes.

Revision ID: 20260712_0002
Revises: 20260712_0001
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260712_0002"
down_revision: str | None = "20260712_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("posting_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("application_url", sa.Text(), nullable=False),
        sa.Column("resume_used", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["posting_id"], ["postings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("posting_id"),
    )
    op.create_index("ix_applications_posting_id", "applications", ["posting_id"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=False),
        sa.Column("to_status", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_application_events_application_id", "application_events", ["application_id"]
    )

    op.create_table(
        "outcomes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("posting_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=True),
        sa.Column("outcome_type", sa.String(length=50), nullable=False),
        sa.Column("stage_reached", sa.String(length=40), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.ForeignKeyConstraint(["posting_id"], ["postings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id"),
    )
    op.create_index("ix_outcomes_application_id", "outcomes", ["application_id"])
    op.create_index("ix_outcomes_posting_id", "outcomes", ["posting_id"])


def downgrade() -> None:
    op.drop_index("ix_outcomes_posting_id", table_name="outcomes")
    op.drop_index("ix_outcomes_application_id", table_name="outcomes")
    op.drop_table("outcomes")
    op.drop_index("ix_application_events_application_id", table_name="application_events")
    op.drop_table("application_events")
    op.drop_index("ix_applications_posting_id", table_name="applications")
    op.drop_table("applications")
