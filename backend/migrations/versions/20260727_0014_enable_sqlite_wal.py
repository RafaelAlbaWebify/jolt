"""Enable SQLite WAL journal mode.

Revision ID: 20260727_0014
Revises: 20260725_0013
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260727_0014"
down_revision: str | None = "20260725_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _set_sqlite_journal_mode(mode: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    raw_connection = connection.connection.driver_connection
    previous_isolation_level = raw_connection.isolation_level
    try:
        raw_connection.isolation_level = None
        result = raw_connection.execute(f"PRAGMA journal_mode={mode}").fetchone()
        actual = str(result[0]).lower() if result else ""
        if actual != mode.lower():
            raise RuntimeError(
                f"SQLite refused journal mode {mode}; active mode is {actual or '(unknown)'}."
            )
    finally:
        raw_connection.isolation_level = previous_isolation_level


def upgrade() -> None:
    _set_sqlite_journal_mode("WAL")


def downgrade() -> None:
    _set_sqlite_journal_mode("DELETE")
