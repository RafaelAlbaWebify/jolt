"""Store stable portal identities without merging or deleting existing postings.

Revision ID: 20261016_0031
Revises: 20261007_0030
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261016_0031"
down_revision = "20261007_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "posting_source_identities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("posting_id", sa.String(length=36), sa.ForeignKey("postings.id"), nullable=False),
        sa.Column("portal", sa.String(length=40), nullable=False),
        sa.Column("source_job_id", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_document_id",
            sa.String(length=36),
            sa.ForeignKey("source_documents.id"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "portal", "source_job_id", name="uq_posting_source_identity_portal_job"
        ),
    )
    op.create_index(
        "ix_posting_source_identities_posting_id",
        "posting_source_identities",
        ["posting_id"],
    )
    op.create_index(
        "ix_posting_source_identities_portal",
        "posting_source_identities",
        ["portal"],
    )


def downgrade() -> None:
    op.drop_index("ix_posting_source_identities_portal", table_name="posting_source_identities")
    op.drop_index("ix_posting_source_identities_posting_id", table_name="posting_source_identities")
    op.drop_table("posting_source_identities")
