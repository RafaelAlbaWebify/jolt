"""Add pre-application decisioning and company watch.

Revision ID: 20260929_0026
Revises: 20260923_0025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260929_0026"
down_revision = "20260923_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ai_reviews") as batch:
        batch.add_column(sa.Column("pre_application_decision", sa.String(length=50), nullable=False, server_default=""))
        batch.add_column(sa.Column("remote_scope", sa.String(length=30), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("work_authorization_status", sa.String(length=20), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("conditions_status", sa.String(length=20), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("official_source_status", sa.String(length=20), nullable=False, server_default="not_checked"))
        batch.add_column(sa.Column("official_source_url", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("official_source_location", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("official_source_evidence_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("experience_evidence_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("questions_for_user_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("company_watch", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("company_watch_reason", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("company_watch_role_patterns_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("recommended_cv_master_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("recommended_certifications_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("linkedin_skill_suggestions_json", sa.Text(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("certification_inventory_complete", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "company_watch",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("company_key", sa.String(length=300), nullable=False),
        sa.Column("source_posting_id", sa.String(length=36), sa.ForeignKey("postings.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("role_patterns_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_key", name="uq_company_watch_company_key"),
    )
    op.create_index("ix_company_watch_company_key", "company_watch", ["company_key"])
    op.create_index("ix_company_watch_source_posting_id", "company_watch", ["source_posting_id"])
    op.create_index("ix_company_watch_active", "company_watch", ["active"])


def downgrade() -> None:
    op.drop_table("company_watch")
    with op.batch_alter_table("ai_reviews") as batch:
        batch.drop_column("certification_inventory_complete")
        batch.drop_column("linkedin_skill_suggestions_json")
        batch.drop_column("recommended_certifications_json")
        batch.drop_column("recommended_cv_master_json")
        batch.drop_column("company_watch_role_patterns_json")
        batch.drop_column("company_watch_reason")
        batch.drop_column("company_watch")
        batch.drop_column("questions_for_user_json")
        batch.drop_column("experience_evidence_json")
        batch.drop_column("official_source_evidence_json")
        batch.drop_column("official_source_location")
        batch.drop_column("official_source_url")
        batch.drop_column("official_source_status")
        batch.drop_column("conditions_status")
        batch.drop_column("work_authorization_status")
        batch.drop_column("remote_scope")
        batch.drop_column("pre_application_decision")
