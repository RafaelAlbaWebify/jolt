from __future__ import annotations

import sqlite3
from pathlib import Path
from zipfile import ZipFile

import pytest

from jolt.backup import create_backup, inspect_backup, restore_backup


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


def test_backup_verifies_and_restores_without_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "jolt.db"
    archive = tmp_path / "JOLT_BACKUP.zip"
    restored = tmp_path / "restored" / "jolt.db"
    _database(source)

    created = create_backup(source, archive)
    verified = inspect_backup(archive)
    restored_manifest = restore_backup(archive, restored)

    assert created == verified == restored_manifest
    assert created["alembic_revision"] == "20260714_0007"
    assert created["source_path_included"] is False
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM evidence").fetchone() == ("preserved",)

    with pytest.raises(FileExistsError):
        restore_backup(archive, restored)


def test_backup_rejects_tampered_database(tmp_path: Path) -> None:
    source = tmp_path / "jolt.db"
    archive = tmp_path / "JOLT_BACKUP.zip"
    _database(source)
    create_backup(source, archive)

    tampered = tmp_path / "tampered.zip"
    with ZipFile(archive) as original, ZipFile(tampered, "w") as replacement:
        replacement.writestr("manifest.json", original.read("manifest.json"))
        replacement.writestr("jolt.db", original.read("jolt.db") + b"tamper")

    with pytest.raises(ValueError, match="hash"):
        inspect_backup(tampered)
