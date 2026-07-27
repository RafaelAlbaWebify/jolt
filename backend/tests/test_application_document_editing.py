from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{path.as_posix()}"))


def _application(client: TestClient) -> str:
    intake = client.post(
        "/api/intake/manual",
        json={
            "raw_text": (
                "Application Support Engineer\nExample Systems\nLocation: Remote Spain\n"
                "Application support, SQL, incident ownership and API troubleshooting."
            )
        },
    ).json()
    client.post(
        f"/api/opportunities/{intake['posting_id']}/reviews",
        json={"evaluation_id": intake["evaluation_id"], "decision": "pursue"},
    )
    created = client.post(
        f"/api/opportunities/{intake['posting_id']}/applications",
        json={"notes": "Prepare application evidence."},
    )
    assert created.status_code == 200
    return created.json()["application_id"]


def test_document_edit_persists_and_records_changed_fields(tmp_path: Path) -> None:
    database = tmp_path / "document-edit.db"
    client = _client(database)
    application_id = _application(client)
    created = client.post(
        f"/api/applications/{application_id}/documents",
        json={
            "document_type": "resume",
            "title": "Support resume",
            "file_path": "C:/resume-v1.pdf",
            "source_url": "https://example.test/resume-v1",
            "status": "ready",
            "notes": "First tailored version.",
        },
    )
    assert created.status_code == 200
    document = created.json()

    updated = client.post(
        f"/api/application-documents/{document['document_id']}/update",
        json={
            "document_type": "resume",
            "title": "Support resume final",
            "file_path": "C:/resume-v2.pdf",
            "source_url": "https://example.test/resume-v2",
            "status": "submitted",
            "notes": "Submitted version.",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "submitted"

    restarted = _client(database)
    saved = restarted.get(f"/api/applications/{application_id}/documents").json()[0]
    assert saved["title"] == "Support resume final"
    event = restarted.get(f"/api/applications/{application_id}").json()["events"][-1]
    assert event["event_type"] == "document_updated"
    assert "title: Support resume -> Support resume final" in event["notes"]
    assert "status: ready -> submitted" in event["notes"]
    assert "file_path: C:/resume-v1.pdf -> C:/resume-v2.pdf" in event["notes"]
