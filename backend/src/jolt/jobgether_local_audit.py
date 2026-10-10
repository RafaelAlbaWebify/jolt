"""Read-only Jobgether identity audit against existing local JOLT records."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def known_jobgether_ids(db_path: Path, source_ids: list[str]) -> set[str]:
    """Return known source IDs; refuse to infer 'new' if the DB is unavailable."""
    if not source_ids:
        return set()
    if not db_path.is_file():
        raise FileNotFoundError(f"JOLT database not found: {db_path}")
    with sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True) as conn:
        placeholders = ",".join("?" for _ in source_ids)
        rows = conn.execute(
            "SELECT DISTINCT item.source_job_id FROM capture_items AS item "
            "JOIN capture_runs AS run ON run.id = item.capture_run_id "
            "WHERE run.source = 'jobgether' "
            f"AND item.source_job_id IN ({placeholders})",
            source_ids,
        ).fetchall()
    return {str(row[0]) for row in rows}


def audit_preview(db_path: Path, jobs: list[dict]) -> dict:
    """Classify source-exact matches only; do not write or alter Review Inbox."""
    ids = [
        job["source_job_id"]
        for job in jobs
        if isinstance(job.get("source_job_id"), str) and not job.get("identity_mismatch")
    ]
    known = known_jobgether_ids(db_path, ids)
    rows = []
    for job in jobs:
        source_id = job.get("source_job_id")
        if source_id is None or job.get("identity_mismatch"):
            status = "identity_unresolved"
        elif job.get("identity_status") == "repeated_in_response":
            status = "repeated_in_response"
        elif source_id in known:
            status = "known_jobgether_source_id"
        else:
            status = "not_seen_in_jobgether_captures"
        rows.append({"source_job_id": source_id, "audit_status": status})
    return {"source": "jobgether", "read_only": True, "jobs": rows}
