"""Add durable Market Intelligence observations

Revision ID: 20260811_0019
Revises: 20260730_0018
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0019"
down_revision: str | None = "20260730_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_intelligence_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "source_capture_run_id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "source_job_id",
            sa.String(length=100),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "posting_identity_key",
            sa.String(length=2110),
            nullable=False,
        ),
        sa.Column(
            "source_url",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "company",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "location",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "engine_version",
            sa.String(length=40),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "recommendation",
            sa.String(length=40),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "confidence",
            sa.String(length=20),
            nullable=False,
            server_default="",
        ),
        sa.Column("ranking_score", sa.Integer(), nullable=True),
        sa.Column(
            "reasons_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_capture_run_id",
            "source_job_id",
            name="uq_market_observation_capture_job",
        ),
    )

    op.create_index(
        "ix_market_intelligence_observations_source_capture_run_id",
        "market_intelligence_observations",
        ["source_capture_run_id"],
    )
    op.create_index(
        "ix_market_intelligence_observations_source_job_id",
        "market_intelligence_observations",
        ["source_job_id"],
    )
    op.create_index(
        "ix_market_intelligence_observations_posting_identity_key",
        "market_intelligence_observations",
        ["posting_identity_key"],
    )
    op.create_index(
        "ix_market_intelligence_observations_captured_at",
        "market_intelligence_observations",
        ["captured_at"],
    )
    op.create_index(
        "ix_market_intelligence_observations_observed_at",
        "market_intelligence_observations",
        ["observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_intelligence_observations_observed_at",
        table_name="market_intelligence_observations",
    )
    op.drop_index(
        "ix_market_intelligence_observations_captured_at",
        table_name="market_intelligence_observations",
    )
    op.drop_index(
        "ix_market_intelligence_observations_posting_identity_key",
        table_name="market_intelligence_observations",
    )
    op.drop_index(
        "ix_market_intelligence_observations_source_job_id",
        table_name="market_intelligence_observations",
    )
    op.drop_index(
        "ix_market_intelligence_observations_source_capture_run_id",
        table_name="market_intelligence_observations",
    )
    op.drop_table("market_intelligence_observations")
