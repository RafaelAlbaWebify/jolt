from __future__ import annotations

import sqlite3
from pathlib import Path

from jolt.backup_audit import run_backup_restore_drill


def _database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('20260714_0007')")
        connection.execute("CREATE TABLE evidence (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence(value) VALUES ('preserved')")
        connection.commit()
    finally:
        connection.close()


def test_backup_restore_audit_writes_privacy_safe_result(tmp_path: Path) -> None:
    database = tmp_path / "jolt.db"
    output = tmp_path / "audit"
    _database(database)

    result = run_backup_restore_drill(database, output)

    assert result["status"] == "passed"
    assert result["alembic_revision"] == "20260714_0007"
    assert result["source_path_included"] is False
    assert result["backup_archive_included"] is False
    assert result["restored_database_included"] is False
    assert result["temporary_artifacts_removed"] is True
    assert len(str(result["database_sha256"])) == 64

    payload = (output / "backup-restore-audit.json").read_text(encoding="utf-8")
    assert str(database.resolve()) not in payload
    assert not list(output.glob("*.zip"))
    assert not list(output.glob("*.db"))
