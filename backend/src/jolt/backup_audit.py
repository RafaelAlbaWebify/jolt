from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from jolt.backup import create_backup, inspect_backup, restore_backup


def run_backup_restore_drill(database_path: Path, output_dir: Path) -> dict[str, object]:
    database = database_path.resolve()
    destination = output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="jolt-backup-audit-") as temporary:
        workspace = Path(temporary)
        backup_path = workspace / "JOLT_BACKUP_AUDIT.zip"
        restored_path = workspace / "restored" / "jolt.db"

        created = create_backup(database, backup_path)
        verified = inspect_backup(backup_path)
        restored = restore_backup(backup_path, restored_path)

        if created != verified or verified != restored:
            raise ValueError("Backup, verification, and restore manifests do not match.")

        result: dict[str, object] = {
            "status": "passed",
            "backup_format": created["format"],
            "database_sha256": created["database_sha256"],
            "database_size": created["database_size"],
            "alembic_revision": created["alembic_revision"],
            "source_path_included": created["source_path_included"],
            "backup_archive_included": False,
            "restored_database_included": False,
            "temporary_artifacts_removed": True,
        }

    output_path = destination / "backup-restore-audit.json"
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a non-destructive JOLT backup/restore drill.")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    result = run_backup_restore_drill(arguments.database, arguments.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
