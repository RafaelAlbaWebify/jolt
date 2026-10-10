from __future__ import annotations

import sqlite3

import pytest

from jolt.jobgether_local_audit import audit_preview, known_jobgether_ids


def test_readonly_jobgether_id_audit(tmp_path) -> None:
    db = tmp_path / "jolt.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE capture_runs (id TEXT, source TEXT)")
        con.execute("CREATE TABLE capture_items (capture_run_id TEXT, source_job_id TEXT)")
        con.executemany(
            "INSERT INTO capture_runs VALUES (?, ?)",
            [("a", "jobgether"), ("b", "indeed")],
        )
        con.executemany(
            "INSERT INTO capture_items VALUES (?, ?)",
            [("a", "known"), ("b", "indeedonly")],
        )
    assert known_jobgether_ids(db, ["known", "indeedonly"]) == {"known"}
    result = audit_preview(
        db,
        [
            {"source_job_id": "known", "identity_status": "observed_unverified"},
            {"source_job_id": "new", "identity_status": "observed_unverified"},
            {"source_job_id": None, "identity_mismatch": True},
        ],
    )
    assert [row["audit_status"] for row in result["jobs"]] == [
        "known_jobgether_source_id",
        "not_seen_in_jobgether_captures",
        "identity_unresolved",
    ]


def test_audit_requires_real_db(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        known_jobgether_ids(tmp_path / "missing.db", ["known"])
