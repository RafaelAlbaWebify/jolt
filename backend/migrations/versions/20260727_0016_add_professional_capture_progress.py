"""Add professional capture progress and cancellation state.

Revision ID: 20260727_0016
Revises: 20260727_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0016"
down_revision: str | None = "20260727_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "professional_capture_runs",
        sa.Column("source_progress_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "professional_capture_runs",
        sa.Column("completed_source_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "professional_capture_runs",
        sa.Column("current_source_id", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "professional_capture_runs",
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "professional_capture_runs",
        sa.Column("progress_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("professional_capture_runs") as batch_op:
        batch_op.drop_column("progress_updated_at")
        batch_op.drop_column("cancel_requested")
        batch_op.drop_column("current_source_id")
        batch_op.drop_column("completed_source_count")
        batch_op.drop_column("source_progress_json")
