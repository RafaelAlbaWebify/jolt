from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(database: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database.as_posix()}"))


def test_canonical_url_duplicate_keeps_one_posting_and_two_sources(tmp_path: Path) -> None:
    database = tmp_path / "canonical.db"
    client = _client(database)
    first = client.post(
        "/api/intake/manual",
        json={
            "source_type": "manual",
            "source_url": "https://example.test/jobs/42?utm_source=first",
            "raw_text": "Support Engineer\nExample\nLocation: Spain\nSQL and incident support.",
        },
    )
    second = client.post(
        "/api/intake/manual",
        json={
            "source_type": "manual",
            "source_url": "https://example.test/jobs/42?utm_source=second",
            "raw_text": "Updated advert text from a second observation.",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["identity_status"] == "confirmed_duplicate"
    assert second.json()["posting_id"] == first.json()["posting_id"]
    assert second.json()["source_document_id"] != first.json()["source_document_id"]

    with sqlite3.connect(database) as connection:
        posting_count = connection.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
        source_count = connection.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
        identity_key = connection.execute("SELECT identity_key FROM postings").fetchone()[0]

    assert posting_count == 1
    assert source_count == 2
    assert identity_key == "url:https://example.test/jobs/42"


def test_content_hash_duplicate_without_url_uses_database_identity(tmp_path: Path) -> None:
    database = tmp_path / "hash.db"
    client = _client(database)
    payload = {
        "source_type": "manual",
        "source_url": "",
        "raw_text": "Application Support Engineer\nExample\nLocation: Remote\nSQL and API support.",
    }

    first = client.post("/api/intake/manual", json=payload)
    second = client.post("/api/intake/manual", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["identity_status"] == "confirmed_duplicate"
    assert second.json()["posting_id"] == first.json()["posting_id"]

    with sqlite3.connect(database) as connection:
        identity_key = connection.execute("SELECT identity_key FROM postings").fetchone()[0]
        index_rows = connection.execute("PRAGMA index_list(postings)").fetchall()

    assert identity_key.startswith("hash:")
    assert any(row[1] == "uq_postings_identity_key" and row[2] == 1 for row in index_rows)


def test_identity_key_and_duplicate_evidence_survive_restart(tmp_path: Path) -> None:
    database = tmp_path / "restart.db"
    first_client = _client(database)
    payload = {
        "source_type": "manual",
        "source_url": "https://example.test/jobs/restart",
        "raw_text": "Production Support Engineer\nExample\nLocation: Remote Spain\nIncident ownership.",
    }
    created = first_client.post("/api/intake/manual", json=payload)
    assert created.status_code == 200

    restarted = _client(database)
    duplicate = restarted.post("/api/intake/manual", json=payload)

    assert duplicate.status_code == 200
    assert duplicate.json()["identity_status"] == "confirmed_duplicate"
    assert duplicate.json()["posting_id"] == created.json()["posting_id"]
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "20260827_0021",
        )
        assert connection.execute("SELECT COUNT(*) FROM postings").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM source_documents").fetchone() == (2,)
