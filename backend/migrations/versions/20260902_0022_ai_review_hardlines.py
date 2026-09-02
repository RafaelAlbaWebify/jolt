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


def upgrade() -> None:
    with op.batch_alter_table("ai_reviews") as batch_op:
        batch_op.alter_column(
            "technical_fit",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column(
                "hardline_status", sa.String(length=20), nullable=False, server_default="PASS"
            )
        )
        batch_op.add_column(
            sa.Column("hardline_reasons_json", sa.Text(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column(
                "location_eligibility",
                sa.String(length=20),
                nullable=False,
                server_default="unknown",
            )
        )
        batch_op.add_column(
            sa.Column("location_evidence_json", sa.Text(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("mandatory_requirements_json", sa.Text(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column(
                "mandatory_requirement_results_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
        batch_op.add_column(
            sa.Column("employment_constraints_json", sa.Text(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column(
                "fit_analysis_allowed", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )
        batch_op.add_column(
            sa.Column("decision_reason", sa.Text(), nullable=False, server_default="")
        )


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
