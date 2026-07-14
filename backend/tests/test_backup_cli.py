from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def _database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('20260714_0007')")
        connection.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES ('preserved')")
        connection.commit()


def _run(*arguments: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-m", "jolt.backup", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_backup_cli_create_verify_and_restore(tmp_path: Path) -> None:
    source = tmp_path / "jolt.db"
    backup = tmp_path / "JOLT_BACKUP.zip"
    restored = tmp_path / "restored" / "jolt.db"
    _database(source)

    created = _run("create", "--database", str(source), "--output", str(backup))
    verified = _run("verify", "--backup", str(backup))
    restored_manifest = _run("restore", "--backup", str(backup), "--target", str(restored))

    assert created == verified == restored_manifest
    assert restored.is_file()
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM evidence").fetchone() == ("preserved",)
