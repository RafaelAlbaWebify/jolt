from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from jolt.backup import create_backup, restore_backup
from jolt.main import create_app


def _client(path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{path.as_posix()}"))


def _application(client: TestClient) -> str:
    intake = client.post(
        "/api/intake/manual",
        json={
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Application support, SQL, incident ownership and API troubleshooting."
            )
        },
    )
    assert intake.status_code == 200
    intake_payload = intake.json()

    review = client.post(
        f"/api/opportunities/{intake_payload['posting_id']}/reviews",
        json={
            "evaluation_id": intake_payload["evaluation_id"],
            "decision": "pursue",
        },
    )
    assert review.status_code == 200

    application = client.post(
        f"/api/opportunities/{intake_payload['posting_id']}/applications",
        json={"notes": "Prepare application evidence."},
    )
    assert application.status_code == 200
    return application.json()["application_id"]


def test_document_file_is_owned_by_jolt_and_survives_restart_and_backup(
    tmp_path: Path,
) -> None:
    database = tmp_path / "documents.db"
    client = _client(database)
    application_id = _application(client)

    created = client.post(
        f"/api/applications/{application_id}/documents",
        json={
            "document_type": "resume",
            "title": "Tailored support resume",
            "file_path": "",
            "source_url": "",
            "status": "ready",
            "notes": "Tailored application version.",
        },
    )
    assert created.status_code == 200
    document = created.json()

    assert document["has_file"] is False
    assert document["stored_filename"] == ""
    assert document["file_size"] == 0

    content = b"%PDF-1.7\nJOLT durable resume evidence\n%%EOF\n"
    digest = hashlib.sha256(content).hexdigest()

    uploaded = client.post(
        f"/api/application-documents/{document['document_id']}/file",
        params={"filename": "Rafael-Alba-Resume.pdf"},
        content=content,
        headers={"Content-Type": "application/pdf"},
    )
    assert uploaded.status_code == 200

    stored = uploaded.json()
    assert stored["has_file"] is True
    assert stored["stored_filename"] == "Rafael-Alba-Resume.pdf"
    assert stored["mime_type"] == "application/pdf"
    assert stored["file_size"] == len(content)
    assert stored["file_sha256"] == digest

    metadata_update = client.post(
        f"/api/application-documents/{document['document_id']}/update",
        json={
            "document_type": "resume",
            "title": "Tailored support resume - submitted",
            "file_path": "",
            "source_url": "",
            "status": "submitted",
            "notes": "Submitted through employer portal.",
        },
    )
    assert metadata_update.status_code == 200
    assert metadata_update.json()["file_sha256"] == digest
    assert metadata_update.json()["has_file"] is True

    restarted = _client(database)

    listed = restarted.get(f"/api/applications/{application_id}/documents")
    assert listed.status_code == 200
    assert listed.json()[0]["stored_filename"] == "Rafael-Alba-Resume.pdf"
    assert listed.json()[0]["file_sha256"] == digest

    downloaded = restarted.get(f"/api/application-documents/{document['document_id']}/file")
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert "Rafael-Alba-Resume.pdf" in downloaded.headers["content-disposition"]

    backup = tmp_path / "jolt-backup.zip"
    restored_database = tmp_path / "restored.db"

    create_backup(database, backup)
    restore_backup(backup, restored_database)

    restored = _client(restored_database)
    restored_download = restored.get(f"/api/application-documents/{document['document_id']}/file")

    assert restored_download.status_code == 200
    assert restored_download.content == content

    timeline = restored.get(f"/api/applications/{application_id}").json()["events"]

    assert "document_file_stored" in {event["event_type"] for event in timeline}


def test_document_file_validates_extension_and_size(tmp_path: Path) -> None:
    client = _client(tmp_path / "validation.db")
    application_id = _application(client)

    created = client.post(
        f"/api/applications/{application_id}/documents",
        json={
            "document_type": "cover_letter",
            "title": "Cover letter",
            "file_path": "",
            "source_url": "",
            "status": "draft",
            "notes": "",
        },
    )
    assert created.status_code == 200
    document_id = created.json()["document_id"]

    invalid_extension = client.post(
        f"/api/application-documents/{document_id}/file",
        params={"filename": "cover-letter.exe"},
        content=b"not executable",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert invalid_extension.status_code == 422

    oversized = client.post(
        f"/api/application-documents/{document_id}/file",
        params={"filename": "cover-letter.pdf"},
        content=b"x" * ((10 * 1024 * 1024) + 1),
        headers={"Content-Type": "application/pdf"},
    )
    assert oversized.status_code == 413

    missing_file = client.get(f"/api/application-documents/{document_id}/file")
    assert missing_file.status_code == 404
