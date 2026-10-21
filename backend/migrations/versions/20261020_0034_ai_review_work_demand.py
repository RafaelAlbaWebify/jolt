"""Persist work-demand evidence alongside AI review decisions.

Revision ID: 20261020_0034
Revises: 20261016_0033
"""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0034"
down_revision = "20261016_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, type_, default in (
        ("employment_track", sa.String(24), "unknown"),
        ("physical_demand_status", sa.String(24), "uncertain"),
        ("physical_demand_evidence_json", sa.Text(), "[]"),
        ("commercial_pressure_status", sa.String(24), "uncertain"),
        ("commercial_pressure_evidence_json", sa.Text(), "[]"),
    ):
        op.add_column("ai_reviews", sa.Column(name, type_, nullable=False, server_default=default))


def downgrade() -> None:
    for name in (
        "commercial_pressure_evidence_json",
        "commercial_pressure_status",
        "physical_demand_evidence_json",
        "physical_demand_status",
        "employment_track",
    ):
        op.drop_column("ai_reviews", name)
