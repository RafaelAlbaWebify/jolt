"""Record confirmed cross-portal duplicates without merging postings.

Revision ID: 20261016_0032
Revises: 20261016_0031
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261016_0032"
down_revision = "20261016_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "confirmed_duplicate_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "first_posting_id", sa.String(length=36), sa.ForeignKey("postings.id"), nullable=False
        ),
        sa.Column(
            "second_posting_id", sa.String(length=36), sa.ForeignKey("postings.id"), nullable=False
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "first_posting_id", "second_posting_id", name="uq_confirmed_duplicate_pair"
        ),
        sa.CheckConstraint(
            "first_posting_id < second_posting_id",
            name="ck_confirmed_duplicate_pair_order",
        ),
    )
    op.create_index(
        "ix_confirmed_duplicate_links_first_posting_id",
        "confirmed_duplicate_links",
        ["first_posting_id"],
    )
    op.create_index(
        "ix_confirmed_duplicate_links_second_posting_id",
        "confirmed_duplicate_links",
        ["second_posting_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_confirmed_duplicate_links_second_posting_id",
        table_name="confirmed_duplicate_links",
    )
    op.drop_index(
        "ix_confirmed_duplicate_links_first_posting_id",
        table_name="confirmed_duplicate_links",
    )
    op.drop_table("confirmed_duplicate_links")
