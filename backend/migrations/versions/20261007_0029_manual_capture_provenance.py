"""Backfill manual intake capture provenance.

Revision ID: 20261007_0029
Revises: 20261006_0028
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "20261007_0029"
down_revision = "20261006_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    required_tables = {"postings", "source_documents", "capture_items", "capture_runs"}
    if not required_tables.issubset(set(inspector.get_table_names())):
        return

    rows = (
        connection.execute(
            sa.text(
                """
            SELECT p.id AS posting_id,
                   p.canonical_url,
                   p.title,
                   p.company,
                   p.location,
                   p.source_document_id,
                   s.source_url,
                   s.captured_at
            FROM postings p
            JOIN source_documents s ON s.id = p.source_document_id
            WHERE s.source_type = 'manual'
              AND NOT EXISTS (
                  SELECT 1 FROM capture_items ci WHERE ci.posting_id = p.id
              )
            """
            )
        )
        .mappings()
        .all()
    )

    for row in rows:
        run_id = str(uuid4())
        connection.execute(
            sa.text(
                """
                INSERT INTO capture_runs
                    (id, source, mode, status, search_url, warnings_json,
                     requested_item_limit, observed_item_count, stop_reason,
                     started_at, completed_at)
                VALUES
                    (:id, 'manual', 'manual', 'completed', :search_url, '[]',
                     1, 1, 'manual_intake_backfill', :started_at, :completed_at)
                """
            ),
            {
                "id": run_id,
                "search_url": row["source_url"] or row["canonical_url"] or "",
                "started_at": row["captured_at"],
                "completed_at": row["captured_at"],
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO capture_items
                    (id, capture_run_id, source_job_id, source_url, title, company,
                     location, detail_status, verification_reasons_json,
                     source_document_id, posting_id)
                VALUES
                    (:id, :capture_run_id, :source_job_id, :source_url, :title, :company,
                     :location, 'verified', '[]', :source_document_id, :posting_id)
                """
            ),
            {
                "id": str(uuid4()),
                "capture_run_id": run_id,
                "source_job_id": row["posting_id"],
                "source_url": row["source_url"] or row["canonical_url"] or "",
                "title": row["title"] or "",
                "company": row["company"] or "",
                "location": row["location"] or "",
                "source_document_id": row["source_document_id"],
                "posting_id": row["posting_id"],
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    run_ids = [
        row[0]
        for row in connection.execute(
            sa.text(
                "SELECT id FROM capture_runs "
                "WHERE source='manual' AND stop_reason='manual_intake_backfill'"
            )
        ).all()
    ]
    for run_id in run_ids:
        connection.execute(
            sa.text("DELETE FROM capture_items WHERE capture_run_id = :run_id"),
            {"run_id": run_id},
        )
        connection.execute(
            sa.text("DELETE FROM capture_runs WHERE id = :run_id"),
            {"run_id": run_id},
        )
