"""Track discovery execution progress.

Revision ID: 20261007_0030
Revises: 20261007_0029
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261007_0030"
down_revision = "20261007_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("discovery_executions"):
        return

    columns = {column["name"] for column in inspector.get_columns("discovery_executions")}
    with op.batch_alter_table("discovery_executions") as batch:
        if "current_page" not in columns:
            batch.add_column(sa.Column("current_page", sa.Integer(), nullable=False, server_default="0"))
        if "pages_visited" not in columns:
            batch.add_column(sa.Column("pages_visited", sa.Integer(), nullable=False, server_default="0"))
        if "captured_count" not in columns:
            batch.add_column(sa.Column("captured_count", sa.Integer(), nullable=False, server_default="0"))
        if "target_jobs" not in columns:
            batch.add_column(sa.Column("target_jobs", sa.Integer(), nullable=False, server_default="0"))
        if "max_pages" not in columns:
            batch.add_column(sa.Column("max_pages", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("discovery_executions"):
        return

    columns = {column["name"] for column in inspector.get_columns("discovery_executions")}
    with op.batch_alter_table("discovery_executions") as batch:
        for name in ("max_pages", "target_jobs", "captured_count", "pages_visited", "current_page"):
            if name in columns:
                batch.drop_column(name)
