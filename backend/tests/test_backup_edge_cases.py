from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile

import pytest

from jolt.backup import create_backup, inspect_backup


def _database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('20260714_0007')")
        connection.commit()


def test_backup_rejects_unexpected_archive_entries(tmp_path: Path) -> None:
    source = tmp_path / "jolt.db"
    backup = tmp_path / "backup.zip"
    _database(source)
    create_backup(source, backup)

    invalid = tmp_path / "invalid.zip"
    with ZipFile(backup) as original, ZipFile(invalid, "w") as replacement:
        replacement.writestr("manifest.json", original.read("manifest.json"))
        replacement.writestr("jolt.db", original.read("jolt.db"))
        replacement.writestr("unexpected.txt", "not allowed")

    with pytest.raises(ValueError, match="unexpected or missing"):
        inspect_backup(invalid)


def test_backup_manifest_does_not_include_source_path(tmp_path: Path) -> None:
    source = tmp_path / "private-location" / "jolt.db"
    source.parent.mkdir()
    backup = tmp_path / "backup.zip"
    _database(source)
    create_backup(source, backup)

    with ZipFile(backup) as archive:
        manifest_text = archive.read("manifest.json").decode("utf-8")
        manifest = json.loads(manifest_text)

    assert str(source.resolve()) not in manifest_text
    assert manifest["source_path_included"] is False
