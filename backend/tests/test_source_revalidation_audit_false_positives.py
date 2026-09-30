from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


SCHEMA = """
CREATE TABLE source_documents (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    raw_text TEXT NOT NULL
);
CREATE TABLE postings (
    id TEXT PRIMARY KEY,
    source_document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    canonical_url TEXT NOT NULL
);
CREATE TABLE ai_reviews (
    id TEXT PRIMARY KEY,
    capture_run_id TEXT NOT NULL,
    posting_id TEXT NOT NULL,
    source_job_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    geography_status TEXT NOT NULL,
    location_eligibility TEXT NOT NULL,
    technical_fit INTEGER,
    reviewed_at TEXT NOT NULL,
    source_conflict INTEGER NOT NULL,
    linkedin_work_model TEXT NOT NULL,
    official_work_model TEXT NOT NULL,
    authoritative_source TEXT NOT NULL,
    official_source_url TEXT NOT NULL,
    remote_status TEXT NOT NULL,
    location_verification_status TEXT NOT NULL,
    source_confidence TEXT NOT NULL
);
"""


def _run(database: Path, output: Path) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit-remote-source-verification.py"
    env = dict(os.environ)
    env["JOLT_DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--days",
            "3650",
            "--revalidation-pack",
            str(output),
            "--max-jobs",
            "10",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _seed(
    path: Path,
    *,
    raw_text: str,
    location: str,
    authority: str,
    remote_status: str,
    verification: str,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT INTO source_documents VALUES (?, ?, ?, ?)",
            ("source-1", "linkedin_live", "https://linkedin.example/1", raw_text),
        )
        connection.execute(
            "INSERT INTO postings VALUES (?, ?, ?, ?, ?, ?)",
            (
                "posting-1",
                "source-1",
                "Systems Administrator",
                "Example",
                location,
                "https://linkedin.example/1",
            ),
        )
        connection.execute(
            """
            INSERT INTO ai_reviews VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                "review-1",
                "capture-1",
                "posting-1",
                "1",
                "pursue",
                "eligible",
                "eligible",
                90,
                "2026-09-30T12:00:00+00:00",
                0,
                "unknown",
                "unknown",
                authority,
                "https://example.test/official" if authority == "official_ats" else "",
                remote_status,
                verification,
                "high" if authority == "official_ats" else "medium",
            ),
        )
        connection.commit()


def test_local_vigo_role_does_not_treat_remote_staff_as_remote_job(tmp_path: Path) -> None:
    database = tmp_path / "local.db"
    output = tmp_path / "local.json"
    _seed(
        database,
        raw_text=(
            "Manage local office connectivity in Vigo and support local and remote staff. "
            "This is an internal systems role."
        ),
        location="Vigo, Galicia, Spain",
        authority="linkedin",
        remote_status="unknown",
        verification="unverified",
    )

    summary = _run(database, output)
    assert summary["positive_candidates"] == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["jobs"] == []


def test_verified_spain_wide_geography_does_not_require_remote_confirmation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "verified.db"
    output = tmp_path / "verified.json"
    _seed(
        database,
        raw_text=(
            "DXC Spain is hiring a Linux systems technician. "
            "Our work model prioritizes in-person collaboration while offering flexibility."
        ),
        location="Spain",
        authority="official_ats",
        remote_status="not_confirmed_remote",
        verification="verified",
    )

    summary = _run(database, output)
    assert summary["positive_candidates"] == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["jobs"] == []
