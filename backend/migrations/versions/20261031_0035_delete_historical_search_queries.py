"""Allow historical search snapshots to outlive saved query configuration.

Revision ID: 20261031_0035
Revises: 20261020_0034
"""

import sqlalchemy as sa
from alembic import op

revision = "20261031_0035"
down_revision = "20261020_0034"
branch_labels = None
depends_on = None

TABLE = "linkedin_discovery_batch_searches"
CONSTRAINT = "fk_linkedin_discovery_batch_searches_saved_search_id_linkedin_saved_searches"


def upgrade() -> None:
    # Keep the original saved_search_id as provenance alongside URL/label snapshots.
    with op.batch_alter_table(
        TABLE,
        naming_convention={"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"},
        reflect_kwargs={"resolve_fks": False},
    ) as batch:
        batch.drop_constraint(CONSTRAINT, type_="foreignkey")


def downgrade() -> None:
    connection = op.get_bind()
    missing = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM linkedin_discovery_batch_searches h "
            "LEFT JOIN linkedin_saved_searches s ON s.id = h.saved_search_id "
            "WHERE s.id IS NULL"
        )
    ).scalar()
    if missing:
        raise RuntimeError(
            "Cannot restore saved-search foreign key after deletion; history is preserved."
        )
    with op.batch_alter_table(TABLE) as batch:
        batch.create_foreign_key(CONSTRAINT, "linkedin_saved_searches", ["saved_search_id"], ["id"])
