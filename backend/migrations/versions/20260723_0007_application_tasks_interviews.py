"""Add application tasks and interviews.

Revision ID: 20260723_0007
Revises: 20260714_0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260723_0007"
down_revision = "20260714_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
    )
    op.create_index(
        "ix_application_tasks_application_id",
        "application_tasks",
        ["application_id"],
    )
    op.create_index(
        "ix_application_tasks_due_at",
        "application_tasks",
        ["due_at"],
    )

    op.create_table(
        "application_interviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("interview_type", sa.String(length=40), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False, server_default="UTC"),
        sa.Column("format_location", sa.Text(), nullable=False, server_default=""),
        sa.Column("participants", sa.Text(), nullable=False, server_default=""),
        sa.Column("preparation_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
    )
    op.create_index(
        "ix_application_interviews_application_id",
        "application_interviews",
        ["application_id"],
    )
    op.create_index(
        "ix_application_interviews_scheduled_at",
        "application_interviews",
        ["scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_application_interviews_scheduled_at", table_name="application_interviews")
    op.drop_index("ix_application_interviews_application_id", table_name="application_interviews")
    op.drop_table("application_interviews")
    op.drop_index("ix_application_tasks_due_at", table_name="application_tasks")
    op.drop_index("ix_application_tasks_application_id", table_name="application_tasks")
    op.drop_table("application_tasks")
