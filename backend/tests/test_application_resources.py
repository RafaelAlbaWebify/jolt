from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{path.as_posix()}"))


def _application(client: TestClient) -> dict[str, object]:
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
    response = client.post(
        f"/api/opportunities/{intake['posting_id']}/applications",
        json={"notes": "Prepare application evidence."},
    )
    assert response.status_code == 200
    return response.json()


def test_contacts_persist_update_and_append_timeline_events(tmp_path: Path) -> None:
    database = tmp_path / "contacts.db"
    client = _client(database)
    application_id = _application(client)["application_id"]

    created = client.post(
        f"/api/applications/{application_id}/contacts",
        json={
            "name": "Morgan Lee",
            "role": "Technical recruiter",
            "company": "Example Systems",
            "email": "morgan@example.test",
            "phone": "+34 600 000 000",
            "linkedin_url": "https://www.linkedin.com/in/morgan-lee",
            "notes": "Initial recruiter screen contact.",
        },
    )
    assert created.status_code == 200
    contact = created.json()
    assert contact["name"] == "Morgan Lee"

    updated = client.post(
        f"/api/application-contacts/{contact['contact_id']}/update",
        json={**contact, "role": "Senior technical recruiter"},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "Senior technical recruiter"

    restarted = _client(database)
    contacts = restarted.get(f"/api/applications/{application_id}/contacts")
    assert contacts.status_code == 200
    assert contacts.json()[0]["email"] == "morgan@example.test"
    timeline = restarted.get(f"/api/applications/{application_id}").json()["events"]
    assert [event["event_type"] for event in timeline[-2:]] == [
        "contact_created",
        "contact_updated",
    ]


def test_documents_persist_update_and_append_timeline_events(tmp_path: Path) -> None:
    database = tmp_path / "documents.db"
    client = _client(database)
    application_id = _application(client)["application_id"]

    created = client.post(
        f"/api/applications/{application_id}/documents",
        json={
            "document_type": "resume",
            "title": "Tailored support resume",
            "file_path": "C:/Users/ralba/Documents/resume.pdf",
            "source_url": "",
            "status": "ready",
            "notes": "Tailored for SQL and API support evidence.",
        },
    )
    assert created.status_code == 200
    document = created.json()
    assert document["status"] == "ready"

    updated = client.post(
        f"/api/application-documents/{document['document_id']}/update",
        json={
            "document_type": "resume",
            "title": "Tailored support resume",
            "file_path": "C:/Users/ralba/Documents/resume.pdf",
            "source_url": "",
            "status": "submitted",
            "notes": "Submitted through the employer portal.",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "submitted"

    restarted = _client(database)
    documents = restarted.get(f"/api/applications/{application_id}/documents")
    assert documents.status_code == 200
    assert documents.json()[0]["document_type"] == "resume"
    timeline = restarted.get(f"/api/applications/{application_id}").json()["events"]
    assert [event["event_type"] for event in timeline[-2:]] == [
        "document_created",
        "document_updated",
    ]


def test_resource_routes_return_not_found_for_unknown_application(tmp_path: Path) -> None:
    client = _client(tmp_path / "missing.db")
    assert client.get("/api/applications/missing/contacts").status_code == 404
    assert client.get("/api/applications/missing/documents").status_code == 404
