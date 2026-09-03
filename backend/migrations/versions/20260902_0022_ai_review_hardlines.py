"""Add two-stage hardline fields to external AI reviews.

Revision ID: 20260902_0022
Revises: 20260827_0021
"""

import sqlalchemy as sa
from alembic import op

revision = "20260902_0022"
down_revision = "20260827_0021"
branch_labels = None
depends_on = None


_HARDLINE_COLUMNS = (
    sa.Column("hardline_status", sa.String(length=20), nullable=False, server_default="PASS"),
    sa.Column("hardline_reasons_json", sa.Text(), nullable=False, server_default="[]"),
    sa.Column(
        "location_eligibility",
        sa.String(length=20),
        nullable=False,
        server_default="unknown",
    ),
    sa.Column("location_evidence_json", sa.Text(), nullable=False, server_default="[]"),
    sa.Column("mandatory_requirements_json", sa.Text(), nullable=False, server_default="[]"),
    sa.Column(
        "mandatory_requirement_results_json",
        sa.Text(),
        nullable=False,
        server_default="[]",
    ),
    sa.Column("employment_constraints_json", sa.Text(), nullable=False, server_default="[]"),
    sa.Column("fit_analysis_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("decision_reason", sa.Text(), nullable=False, server_default=""),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # A few migration-recovery tests intentionally start from a sparse historic
    # schema that is stamped at an old revision but omits capture_runs. SQLite
    # batch reflection follows ai_reviews foreign keys and cannot rebuild that
    # synthetic table graph. Preserve recovery compatibility by adding the new
    # columns directly in that exceptional shape. Real JOLT schemas contain
    # capture_runs and use the full batch migration, including nullable fit.
    if not inspector.has_table("capture_runs"):
        for column in _HARDLINE_COLUMNS:
            op.add_column("ai_reviews", column)
        return

    with op.batch_alter_table("ai_reviews") as batch_op:
        batch_op.alter_column(
            "technical_fit",
            existing_type=sa.Integer(),
            nullable=True,
        )
        for column in _HARDLINE_COLUMNS:
            batch_op.add_column(column)


def downgrade() -> None:
    # Old schema requires an integer. Historic rows that were hardline-rejected
    # under 1.1 receive 0 only during downgrade; production 1.1 semantics never
    # fabricate a fit score.
    op.execute("UPDATE ai_reviews SET technical_fit = 0 WHERE technical_fit IS NULL")
    with op.batch_alter_table("ai_reviews") as batch_op:
        batch_op.drop_column("decision_reason")
        batch_op.drop_column("fit_analysis_allowed")
        batch_op.drop_column("employment_constraints_json")
        batch_op.drop_column("mandatory_requirement_results_json")
        batch_op.drop_column("mandatory_requirements_json")
        batch_op.drop_column("location_evidence_json")
        batch_op.drop_column("location_eligibility")
        batch_op.drop_column("hardline_reasons_json")
        batch_op.drop_column("hardline_status")
        batch_op.alter_column(
            "technical_fit",
            existing_type=sa.Integer(),
            nullable=False,
        )
