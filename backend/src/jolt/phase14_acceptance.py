"""Isolated Windows acceptance for Phase 1.4. Never mutate the operator database."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from jolt.backup import create_backup, inspect_backup, restore_backup
from jolt.database import create_session_factory
from jolt.sources.portal_observation_backfill import backfill_portal_observation_receipts


OWNED = ("applications", "review_decisions", "outcomes", "ai_reviews")
SOURCES = ("posting_source_identities", "portal_source_observations", "capture_items", "capture_runs")


def counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {
            table: int(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            if table in tables else -1
            for table in OWNED + SOURCES
        }


def integrity(path: Path) -> bool:
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
        return db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def accept(source: Path, output: Path) -> dict[str, object]:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"JOLT database not found: {source}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jolt-phase14-") as tmp:
        work = Path(tmp)
        archive = work / "backup.zip"
        restored = work / "restored.db"
        isolated = work / "migrated.db"

        # SQLite's online backup is safe with WAL mode and an active application.
        original = counts(source)
        manifest = create_backup(source, archive)
        assert inspect_backup(archive) == manifest
        restore_backup(archive, restored)
        if not integrity(restored):
            raise RuntimeError("Restored snapshot integrity check failed")
        snapshot_before = counts(restored)
        shutil.copy2(restored, isolated)
        factory = create_session_factory(f"sqlite:///{isolated.as_posix()}")
        with factory() as session:
            dry = backfill_portal_observation_receipts(session).model_dump()
            session.rollback()
        after = counts(isolated)
        if not integrity(isolated):
            raise RuntimeError("Migrated isolated copy failed integrity check")
        if any(after[t] != snapshot_before[t] for t in OWNED):
            raise RuntimeError("Operator-owned applications/reviews changed in the isolated test")
        if after["capture_items"] != snapshot_before["capture_items"]:
            raise RuntimeError("Capture items changed during read-only acceptance")
        if after["capture_runs"] != snapshot_before["capture_runs"]:
            raise RuntimeError("Capture runs changed during read-only acceptance")
        if after["portal_source_observations"] < max(0, snapshot_before["portal_source_observations"]):
            raise RuntimeError("Historical portal receipts were lost")
        if not integrity(restored) or counts(restored) != snapshot_before:
            raise RuntimeError("Restore snapshot changed during isolated migration")
        report: dict[str, object] = {
            "status": "PASS",
            "tested_at_utc": datetime.now(UTC).isoformat(),
            "production_database_modified": False,
            "backup_verified": True,
            "restore_verified": True,
            "isolated_migration_verified": True,
            "integrity_verified": True,
            "owned_rows_preserved": True,
            "source_database_counts_at_start": original,
            "snapshot_counts_before": snapshot_before,
            "isolated_counts_after": after,
            "historical_backfill_dry_run": dry,
            "limitations": [
                "No live portal capture or operator UI acceptance performed",
                "Raw artifact contents are not included in this report",
                "Historical receipts cannot be reconstructed after original artifacts were deleted",
            ],
        }
        dest = output / "JOLT_PHASE_1_4_ACCEPTANCE.json"
        dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return {"status": "PASS", "report": str(dest), "dry_run": dry}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(accept(args.database, args.output), indent=2))


if __name__ == "__main__":
    main()
