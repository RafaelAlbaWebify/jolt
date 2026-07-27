"""Add race-safe posting identity key.

Revision ID: 20260727_0015
Revises: 20260727_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0015"
down_revision: str | None = "20260727_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_postings_identity_key"


def upgrade() -> None:
    op.add_column("postings", sa.Column("identity_key", sa.String(length=2110), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT postings.id, postings.canonical_url, source_documents.content_hash
            FROM postings
            JOIN source_documents ON source_documents.id = postings.source_document_id
            ORDER BY postings.id
            """
        )
    ).mappings()

    seen: dict[str, str] = {}
    for row in rows:
        canonical_url = str(row["canonical_url"] or "").strip()
        content_hash = str(row["content_hash"] or "").strip()
        identity_key = f"url:{canonical_url}" if canonical_url else f"hash:{content_hash}"
        previous_posting_id = seen.get(identity_key)
        if previous_posting_id is not None:
            raise RuntimeError(
                "Cannot add posting identity constraint: postings "
                f"{previous_posting_id} and {row['id']} share {identity_key}."
            )
        seen[identity_key] = str(row["id"])
        connection.execute(
            sa.text("UPDATE postings SET identity_key = :identity_key WHERE id = :posting_id"),
            {"identity_key": identity_key, "posting_id": row["id"]},
        )

    with op.batch_alter_table("postings") as batch_op:
        batch_op.alter_column(
            "identity_key",
            existing_type=sa.String(length=2110),
            nullable=False,
        )
    op.create_index(INDEX_NAME, "postings", ["identity_key"], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="postings")
    with op.batch_alter_table("postings") as batch_op:
        batch_op.drop_column("identity_key")
