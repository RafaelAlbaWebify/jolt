"""Add application readiness reports.

Revision ID: 20260714_0004
Revises: 20260712_0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260714_0004"
down_revision = "20260712_0003"
branch_labels = None
depends_on = None

TABLE_NAME = "application_readiness_reports"
INDEX_NAME = "ix_application_readiness_reports_posting_id"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("posting_id", sa.String(length=36), nullable=False),
            sa.Column("profile_version_id", sa.String(length=80), nullable=False),
            sa.Column("engine_version", sa.String(length=50), nullable=False),
            sa.Column("priority", sa.String(length=20), nullable=False),
            sa.Column("readiness_score", sa.Integer(), nullable=False),
            sa.Column("report_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["posting_id"], ["postings.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(INDEX_NAME, TABLE_NAME, ["posting_id"], unique=False)
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME not in existing_indexes:
        op.create_index(INDEX_NAME, TABLE_NAME, ["posting_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE_NAME):
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME in existing_indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
