"""Add generic saved searches for multi-source discovery.

Revision ID: 20261005_0027
Revises: 20260930_0026
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261005_0027"
down_revision = "20260930_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_saved_searches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("definition_json", sa.Text(), nullable=False),
        sa.Column("definition_key", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_jobs", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source",
            "definition_key",
            name="uq_discovery_saved_search_source_definition",
        ),
    )
    op.create_index(
        "ix_discovery_saved_searches_source",
        "discovery_saved_searches",
        ["source"],
        unique=False,
    )
    op.create_index(
        "ix_discovery_saved_searches_enabled",
        "discovery_saved_searches",
        ["enabled"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_discovery_saved_searches_enabled", table_name="discovery_saved_searches")
    op.drop_index("ix_discovery_saved_searches_source", table_name="discovery_saved_searches")
    op.drop_table("discovery_saved_searches")
