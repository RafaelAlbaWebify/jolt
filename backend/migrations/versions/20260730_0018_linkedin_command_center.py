"""Add LinkedIn command center tables

Revision ID: 20260730_0018
Revises: 20260728_0017
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0018"
down_revision: str | None = "20260728_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "linkedin_presence_captures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("visible_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_capture_id", sa.String(length=36), nullable=True),
        sa.Column(
            "changed_since_previous", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["previous_capture_id"], ["linkedin_presence_captures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_linkedin_presence_captures_category", "linkedin_presence_captures", ["category"]
    )
    op.create_index(
        "ix_linkedin_presence_captures_content_hash", "linkedin_presence_captures", ["content_hash"]
    )
    op.create_index(
        "ix_linkedin_presence_captures_previous_capture_id",
        "linkedin_presence_captures",
        ["previous_capture_id"],
    )

    op.create_table(
        "linkedin_presence_recommendations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_id", sa.String(length=36), nullable=True),
        sa.Column("recommendation_type", sa.String(length=40), nullable=False),
        sa.Column("target_area", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("proposed_action", sa.Text(), nullable=False, server_default=""),
        sa.Column("proposed_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["capture_id"], ["linkedin_presence_captures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_linkedin_presence_recommendations_capture_id",
        "linkedin_presence_recommendations",
        ["capture_id"],
    )
    op.create_index(
        "ix_linkedin_presence_recommendations_priority",
        "linkedin_presence_recommendations",
        ["priority"],
    )
    op.create_index(
        "ix_linkedin_presence_recommendations_recommendation_type",
        "linkedin_presence_recommendations",
        ["recommendation_type"],
    )
    op.create_index(
        "ix_linkedin_presence_recommendations_status",
        "linkedin_presence_recommendations",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_linkedin_presence_recommendations_status",
        table_name="linkedin_presence_recommendations",
    )
    op.drop_index(
        "ix_linkedin_presence_recommendations_recommendation_type",
        table_name="linkedin_presence_recommendations",
    )
    op.drop_index(
        "ix_linkedin_presence_recommendations_priority",
        table_name="linkedin_presence_recommendations",
    )
    op.drop_index(
        "ix_linkedin_presence_recommendations_capture_id",
        table_name="linkedin_presence_recommendations",
    )
    op.drop_table("linkedin_presence_recommendations")
    op.drop_index(
        "ix_linkedin_presence_captures_previous_capture_id", table_name="linkedin_presence_captures"
    )
    op.drop_index(
        "ix_linkedin_presence_captures_content_hash", table_name="linkedin_presence_captures"
    )
    op.drop_index("ix_linkedin_presence_captures_category", table_name="linkedin_presence_captures")
    op.drop_table("linkedin_presence_captures")
