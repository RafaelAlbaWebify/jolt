"""Add capture run audit metadata.

Revision ID: 20260714_0006
Revises: 20260714_0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260714_0006"
down_revision = "20260714_0005"
branch_labels = None
depends_on = None

TABLE_NAME = "capture_runs"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}

    with op.batch_alter_table(TABLE_NAME) as batch:
        if "requested_item_limit" not in columns:
            batch.add_column(sa.Column("requested_item_limit", sa.Integer(), nullable=True))
        if "observed_item_count" not in columns:
            batch.add_column(
                sa.Column(
                    "observed_item_count",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
        if "stop_reason" not in columns:
            batch.add_column(
                sa.Column(
                    "stop_reason",
                    sa.String(length=80),
                    nullable=False,
                    server_default="legacy_unknown",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}

    with op.batch_alter_table(TABLE_NAME) as batch:
        if "stop_reason" in columns:
            batch.drop_column("stop_reason")
        if "observed_item_count" in columns:
            batch.drop_column("observed_item_count")
        if "requested_item_limit" in columns:
            batch.drop_column("requested_item_limit")
