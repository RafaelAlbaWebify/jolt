"""Persist bounded Professional capture options.

Revision ID: 20260728_0017
Revises: 20260727_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0017"
down_revision: str | None = "20260727_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_OPTIONS = (
    '{"max_sources":3,"max_scroll_batches":2,"max_items_per_source":25,'
    '"timeout_seconds":30,"stop_on_failure":true}'
)


def upgrade() -> None:
    op.add_column(
        "professional_capture_runs",
        sa.Column(
            "capture_options_json",
            sa.Text(),
            nullable=False,
            server_default=_DEFAULT_OPTIONS,
        ),
    )


def downgrade() -> None:
    op.drop_column("professional_capture_runs", "capture_options_json")
