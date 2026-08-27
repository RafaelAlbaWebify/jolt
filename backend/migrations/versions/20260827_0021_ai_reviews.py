"""Add durable external AI reviews.

Revision ID: 20260827_0021
Revises: 20260815_0020
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260827_0021"
down_revision = "20260815_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capture_run_id", sa.String(length=36), nullable=False),
        sa.Column("posting_id", sa.String(length=36), nullable=False),
        sa.Column("source_job_id", sa.String(length=100), nullable=False),
        sa.Column("review_source", sa.String(length=40), nullable=False),
        sa.Column("review_version", sa.String(length=80), nullable=False),
        sa.Column("contract_version", sa.String(length=20), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("geography_status", sa.String(length=20), nullable=False),
        sa.Column("clearance_status", sa.String(length=20), nullable=False),
        sa.Column("language_status", sa.String(length=20), nullable=False),
        sa.Column("technical_fit", sa.Integer(), nullable=False),
        sa.Column("duplicate_of_posting_id", sa.String(length=36), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reasons_json", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["capture_run_id"],
            ["capture_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["posting_id"],
            ["postings.id"],
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_posting_id"],
            ["postings.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "capture_run_id",
            "posting_id",
            "review_source",
            name="uq_ai_review_capture_posting_source",
        ),
    )

    op.create_index(
        "ix_ai_reviews_capture_run_id",
        "ai_reviews",
        ["capture_run_id"],
    )
    op.create_index(
        "ix_ai_reviews_posting_id",
        "ai_reviews",
        ["posting_id"],
    )
    op.create_index(
        "ix_ai_reviews_source_job_id",
        "ai_reviews",
        ["source_job_id"],
    )
    op.create_index(
        "ix_ai_reviews_review_source",
        "ai_reviews",
        ["review_source"],
    )
    op.create_index(
        "ix_ai_reviews_decision",
        "ai_reviews",
        ["decision"],
    )
    op.create_index(
        "ix_ai_reviews_duplicate_of_posting_id",
        "ai_reviews",
        ["duplicate_of_posting_id"],
    )
    connection = op.get_bind()
    inspector = inspect(connection)

    if inspector.has_table("review_decisions"):
        review_columns = {column["name"] for column in inspector.get_columns("review_decisions")}

        with op.batch_alter_table("review_decisions") as batch_op:
            if "evaluation_id" in review_columns:
                batch_op.alter_column(
                    "evaluation_id",
                    existing_type=sa.String(length=36),
                    nullable=True,
                )

            if "ai_review_id" not in review_columns:
                batch_op.add_column(
                    sa.Column(
                        "ai_review_id",
                        sa.String(length=36),
                        nullable=True,
                    )
                )
                batch_op.create_foreign_key(
                    "fk_review_decisions_ai_review_id",
                    "ai_reviews",
                    ["ai_review_id"],
                    ["id"],
                )
                batch_op.create_index(
                    "ix_review_decisions_ai_review_id",
                    ["ai_review_id"],
                )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)

    if inspector.has_table("review_decisions"):
        review_columns = {column["name"] for column in inspector.get_columns("review_decisions")}

        if "ai_review_id" in review_columns:
            with op.batch_alter_table("review_decisions") as batch_op:
                batch_op.drop_index(
                    "ix_review_decisions_ai_review_id",
                )
                batch_op.drop_constraint(
                    "fk_review_decisions_ai_review_id",
                    type_="foreignkey",
                )
                batch_op.drop_column("ai_review_id")

        inspector = inspect(connection)
        review_columns = {column["name"] for column in inspector.get_columns("review_decisions")}

        if "evaluation_id" in review_columns:
            with op.batch_alter_table("review_decisions") as batch_op:
                batch_op.alter_column(
                    "evaluation_id",
                    existing_type=sa.String(length=36),
                    nullable=False,
                )

    op.drop_index(
        "ix_ai_reviews_duplicate_of_posting_id",
        table_name="ai_reviews",
    )
    op.drop_index(
        "ix_ai_reviews_decision",
        table_name="ai_reviews",
    )
    op.drop_index(
        "ix_ai_reviews_review_source",
        table_name="ai_reviews",
    )
    op.drop_index(
        "ix_ai_reviews_source_job_id",
        table_name="ai_reviews",
    )
    op.drop_index(
        "ix_ai_reviews_posting_id",
        table_name="ai_reviews",
    )
    op.drop_index(
        "ix_ai_reviews_capture_run_id",
        table_name="ai_reviews",
    )
    op.drop_table("ai_reviews")
