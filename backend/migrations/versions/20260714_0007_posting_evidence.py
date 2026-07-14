"""Add posting evidence linkage.

Revision ID: 20260714_0007
Revises: 20260714_0006
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "20260714_0007"
down_revision = "20260714_0006"
branch_labels = None
depends_on = None

TABLE_NAME = "posting_evidence"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("posting_id", sa.String(length=36), nullable=False),
            sa.Column("source_document_id", sa.String(length=36), nullable=False),
            sa.Column("identity_status", sa.String(length=40), nullable=False),
            sa.Column("match_basis", sa.String(length=40), nullable=False),
            sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["posting_id"], ["postings.id"]),
            sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
            sa.UniqueConstraint("source_document_id"),
        )
        op.create_index(
            "ix_posting_evidence_posting_id", TABLE_NAME, ["posting_id"], unique=False
        )
        op.create_index(
            "ix_posting_evidence_source_document_id",
            TABLE_NAME,
            ["source_document_id"],
            unique=True,
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table("postings") or not inspector.has_table("source_documents"):
        return

    evidence = sa.table(
        TABLE_NAME,
        sa.column("id", sa.String),
        sa.column("posting_id", sa.String),
        sa.column("source_document_id", sa.String),
        sa.column("identity_status", sa.String),
        sa.column("match_basis", sa.String),
        sa.column("linked_at", sa.DateTime(timezone=True)),
    )
    postings = sa.table(
        "postings",
        sa.column("id", sa.String),
        sa.column("source_document_id", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    existing_source_ids = set(bind.execute(sa.select(evidence.c.source_document_id)).scalars())
    for posting_id, source_document_id, created_at in bind.execute(
        sa.select(postings.c.id, postings.c.source_document_id, postings.c.created_at)
    ):
        if source_document_id in existing_source_ids:
            continue
        bind.execute(
            evidence.insert().values(
                id=str(uuid4()),
                posting_id=posting_id,
                source_document_id=source_document_id,
                identity_status="original",
                match_basis="canonical_posting",
                linked_at=created_at,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(TABLE_NAME):
        op.drop_table(TABLE_NAME)
