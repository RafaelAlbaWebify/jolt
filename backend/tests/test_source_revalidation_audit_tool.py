from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _seed_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
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
        )
        connection.execute(
            """
            INSERT INTO source_documents
            (id, source_type, source_url, raw_text)
            VALUES (?, ?, ?, ?)
            """,
            (
                "source-1",
                "linkedin_live",
                "https://www.linkedin.com/jobs/view/1/",
                "This role is Remote and full-time.",
            ),
        )
        connection.execute(
            """
            INSERT INTO postings
            (id, source_document_id, title, company, location, canonical_url)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "posting-1",
                "source-1",
                "Support Engineer",
                "Example",
                "European Union",
                "https://www.linkedin.com/jobs/view/1/",
            ),
        )
        connection.execute(
            """
            INSERT INTO ai_reviews
            (
                id, capture_run_id, posting_id, source_job_id, decision,
                geography_status, location_eligibility, technical_fit, reviewed_at,
                source_conflict, linkedin_work_model, official_work_model,
                authoritative_source, official_source_url, remote_status,
                location_verification_status, source_confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "review-1",
                "capture-1",
                "posting-1",
                "1",
                "pursue",
                "eligible",
                "eligible",
                88,
                "2026-09-30T12:00:00+00:00",
                0,
                "unknown",
                "unknown",
                "unknown",
                "",
                "unknown",
                "unverified",
                "unknown",
            ),
        )
        connection.commit()


def test_revalidation_pack_exports_positive_remote_risk(tmp_path: Path) -> None:
    database = tmp_path / "jolt.db"
    output = tmp_path / "revalidation.json"
    _seed_database(database)

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit-remote-source-verification.py"
    env = dict(os.environ)
    env["JOLT_DATABASE_URL"] = f"sqlite:///{database.as_posix()}"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--days",
            "30",
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
    summary = json.loads(result.stdout)
    assert summary["selected_jobs"] == 1

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["pack_type"] == "jolt_source_revalidation_input"
    assert payload["ai_review_contract_version"] == "1.2"
    assert payload["selection"]["selected_jobs"] == 1
    assert payload["jobs"][0]["posting_id"] == "posting-1"
    assert payload["jobs"][0]["capture_run_id"] == "capture-1"
    assert payload["jobs"][0]["risk_tier"] == 2
    assert "Remote" in payload["jobs"][0]["source_text"]
