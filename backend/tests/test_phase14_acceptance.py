"""Isolated operator acceptance must never change its input database."""

import json
import sqlite3
from types import SimpleNamespace

import jolt.phase14_acceptance as phase14
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


def test_phase14_acceptance_disposes_isolated_database_engine(tmp_path, monkeypatch) -> None:
    original = tmp_path / "jolt.db"
    factory = create_session_factory(f"sqlite:///{original.as_posix()}")
    with factory() as session:
        session.commit()
    factory.kw["bind"].dispose()

    disposed = []
    original_factory = phase14.create_session_factory

    def tracked_factory(url):
        isolated_factory = original_factory(url)
        engine = isolated_factory.kw["bind"]
        original_dispose = engine.dispose

        def dispose():
            disposed.append(True)
            original_dispose()

        monkeypatch.setattr(engine, "dispose", dispose)
        return isolated_factory

    monkeypatch.setattr(phase14, "create_session_factory", tracked_factory)
    assert accept(original, tmp_path / "reports")["status"] == "PASS"
    assert disposed == [True]


def test_integrity_closes_sqlite_file_handle_explicitly(tmp_path, monkeypatch) -> None:
    original = tmp_path / "integrity.db"
    with sqlite3.connect(original) as connection:
        connection.execute("CREATE TABLE proof (id INTEGER PRIMARY KEY)")
    closed: list[bool] = []
    native_connect = sqlite3.connect

    class TrackedConnection:
        def __init__(self, path, **kwargs):
            self.connection = native_connect(path, **kwargs)

        def execute(self, sql):
            return self.connection.execute(sql)

        def close(self):
            closed.append(True)
            self.connection.close()

    monkeypatch.setattr(
        phase14,
        "sqlite3",
        SimpleNamespace(connect=lambda path, **kwargs: TrackedConnection(path, **kwargs)),
    )
    assert phase14.integrity(original) is True
    assert closed == [True]
