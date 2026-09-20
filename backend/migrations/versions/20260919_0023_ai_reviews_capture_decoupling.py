"""Decouple durable AI reviews from raw capture runs.

Revision ID: 20260919_0023
Revises: 20260902_0022
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260919_0023"
down_revision = "20260902_0022"
branch_labels = None
depends_on = None

_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}

_CAPTURE_FK_NAME = "fk_ai_reviews_capture_run_id_capture_runs"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Migration-recovery tests intentionally use a sparse historical schema
    # without capture_runs. In that synthetic shape there is no live parent
    # table to decouple from, and SQLite batch reflection cannot traverse the
    # dangling historic FK metadata. Advancing the revision is sufficient.
    if not inspector.has_table("capture_runs"):
        return

    with op.batch_alter_table(
        "ai_reviews",
        recreate="always",
        naming_convention=_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            _CAPTURE_FK_NAME,
            type_="foreignkey",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("capture_runs"):
        return

    with op.batch_alter_table(
        "ai_reviews",
        recreate="always",
        naming_convention=_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.create_foreign_key(
            _CAPTURE_FK_NAME,
            "capture_runs",
            ["capture_run_id"],
            ["id"],
        )
