"""Isolated operator acceptance must never change its input database."""

import json
import sqlite3

from jolt.database import create_session_factory
from jolt.phase14_acceptance import accept


def test_phase14_acceptance_preserves_original_and_verifies_backup(tmp_path) -> None:
    original = tmp_path / "jolt.db"
    factory = create_session_factory(f"sqlite:///{original.as_posix()}")
    with factory() as session:
        session.commit()
    with sqlite3.connect(original) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    report_dir = tmp_path / "reports"
    result = accept(original, report_dir)
    assert result["status"] == "PASS"
    report = json.loads((report_dir / "JOLT_PHASE_1_4_ACCEPTANCE.json").read_text())
    assert report["backup_verified"] is True
    assert report["restore_verified"] is True
    assert report["production_database_modified"] is False
    assert report["owned_rows_preserved"] is True
    assert report["source_database_counts_at_start"] == report["snapshot_counts_before"]
