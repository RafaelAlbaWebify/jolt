"""Add immutable capture artifacts.

Revision ID: 20260714_0005
Revises: 20260714_0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260714_0005"
down_revision = "20260714_0004"
branch_labels = None
depends_on = None

TABLE_NAME = "capture_artifacts"
ITEM_INDEX = "ix_capture_artifacts_capture_item_id"
HASH_INDEX = "ix_capture_artifacts_content_hash"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(TABLE_NAME):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_item_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["capture_item_id"], ["capture_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("capture_item_id"),
    )
    op.create_index(ITEM_INDEX, TABLE_NAME, ["capture_item_id"], unique=True)
    op.create_index(HASH_INDEX, TABLE_NAME, ["content_hash"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE_NAME):
        return
    op.drop_index(HASH_INDEX, table_name=TABLE_NAME)
    op.drop_index(ITEM_INDEX, table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
