from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

BACKUP_FORMAT = "jolt-sqlite-backup-v1"
DATABASE_ENTRY = "jolt.db"
MANIFEST_ENTRY = "manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_check(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise ValueError(f"SQLite integrity check failed: {result!r}")
    finally:
        connection.close()


def _schema_revision(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT version_num FROM alembic_version ORDER BY version_num LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return "unknown"
    finally:
        connection.close()
    return str(row[0]) if row else "unknown"


def create_backup(database_path: Path, output_path: Path) -> dict[str, object]:
    source = database_path.resolve()
    destination = output_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"JOLT database not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Backup already exists: {destination}")

    with tempfile.TemporaryDirectory(prefix="jolt-backup-") as temporary:
        snapshot = Path(temporary) / DATABASE_ENTRY
        source_connection = sqlite3.connect(source)
        target_connection = sqlite3.connect(snapshot)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()

        _integrity_check(snapshot)
        manifest: dict[str, object] = {
            "format": BACKUP_FORMAT,
            "created_at": datetime.now(UTC).isoformat(),
            "database_entry": DATABASE_ENTRY,
            "database_size": snapshot.stat().st_size,
            "database_sha256": _sha256(snapshot),
            "alembic_revision": _schema_revision(snapshot),
            "source_path_included": False,
        }
        with ZipFile(destination, "x", compression=ZIP_DEFLATED) as archive:
            archive.write(snapshot, DATABASE_ENTRY)
            archive.writestr(MANIFEST_ENTRY, json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def inspect_backup(backup_path: Path) -> dict[str, object]:
    archive_path = backup_path.resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Backup not found: {archive_path}")
    with tempfile.TemporaryDirectory(prefix="jolt-verify-") as temporary:
        root = Path(temporary)
        with ZipFile(archive_path, "r") as archive:
            names = set(archive.namelist())
            if names != {DATABASE_ENTRY, MANIFEST_ENTRY}:
                raise ValueError("Backup contains unexpected or missing entries.")
            manifest = json.loads(archive.read(MANIFEST_ENTRY))
            if manifest.get("format") != BACKUP_FORMAT:
                raise ValueError("Unsupported JOLT backup format.")
            archive.extract(DATABASE_ENTRY, root)
        database = root / DATABASE_ENTRY
        if _sha256(database) != manifest.get("database_sha256"):
            raise ValueError("Backup database hash does not match its manifest.")
        if database.stat().st_size != manifest.get("database_size"):
            raise ValueError("Backup database size does not match its manifest.")
        _integrity_check(database)
        actual_revision = _schema_revision(database)
        if actual_revision != manifest.get("alembic_revision"):
            raise ValueError("Backup schema revision does not match its manifest.")
        return manifest


def restore_backup(backup_path: Path, target_path: Path) -> dict[str, object]:
    target = target_path.resolve()
    if target.exists():
        raise FileExistsError(f"Restore target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = inspect_backup(backup_path)

    with tempfile.TemporaryDirectory(prefix="jolt-restore-") as temporary:
        extracted = Path(temporary) / DATABASE_ENTRY
        with ZipFile(backup_path.resolve(), "r") as archive:
            archive.extract(DATABASE_ENTRY, Path(temporary))
        shutil.copy2(extracted, target)
    try:
        _integrity_check(target)
        if _sha256(target) != manifest["database_sha256"]:
            raise ValueError("Restored database hash does not match the backup manifest.")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, verify, or restore a JOLT SQLite backup.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--database", required=True, type=Path)
    create.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--backup", required=True, type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("--backup", required=True, type=Path)
    restore.add_argument("--target", required=True, type=Path)
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    if arguments.command == "create":
        result = create_backup(arguments.database, arguments.output)
    elif arguments.command == "verify":
        result = inspect_backup(arguments.backup)
    else:
        result = restore_backup(arguments.backup, arguments.target)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
