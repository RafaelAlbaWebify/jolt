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
    response = client.post(
        f"/api/opportunities/{intake['posting_id']}/applications",
        json={"notes": "Prepare application evidence."},
    )
    assert response.status_code == 200
    return response.json()["application_id"]


def test_contact_validation_and_before_after_audit(tmp_path: Path) -> None:
    client = _client(tmp_path / "contacts.db")
    application_id = _application(client)
    created = client.post(
        f"/api/applications/{application_id}/contacts",
        json={
            "name": "  Morgan Lee  ",
            "role": "Technical recruiter",
            "email": "morgan@example.test",
            "linkedin_url": "https://www.linkedin.com/in/morgan-lee",
        },
    )
    assert created.status_code == 200
    contact = created.json()
    assert contact["name"] == "Morgan Lee"

    updated = client.post(
        f"/api/application-contacts/{contact['contact_id']}/update",
        json={**contact, "role": "Senior technical recruiter", "email": "senior@example.test"},
    )
    assert updated.status_code == 200

    timeline = client.get(f"/api/applications/{application_id}").json()["events"]
    correction = timeline[-1]
    assert correction["event_type"] == "contact_updated"
    assert "role: Technical recruiter -> Senior technical recruiter" in correction["notes"]
    assert "email: morgan@example.test -> senior@example.test" in correction["notes"]


def test_optional_contact_fields_reject_invalid_values(tmp_path: Path) -> None:
    client = _client(tmp_path / "validation.db")
    application_id = _application(client)
    endpoint = f"/api/applications/{application_id}/contacts"

    assert (
        client.post(endpoint, json={"name": "Morgan", "email": "", "linkedin_url": ""}).status_code
        == 200
    )
    invalid_email = client.post(endpoint, json={"name": "Morgan", "email": "not-an-email"})
    assert invalid_email.status_code == 422
    assert "valid email address" in invalid_email.text
    insecure = client.post(
        endpoint,
        json={"name": "Morgan", "linkedin_url": "http://www.linkedin.com/in/morgan"},
    )
    assert insecure.status_code == 422
    wrong_host = client.post(
        endpoint,
        json={"name": "Morgan", "linkedin_url": "https://example.test/in/morgan"},
    )
    assert wrong_host.status_code == 422


def test_document_source_url_is_blank_or_public_https(tmp_path: Path) -> None:
    client = _client(tmp_path / "documents.db")
    application_id = _application(client)
    endpoint = f"/api/applications/{application_id}/documents"
    assert (
        client.post(
            endpoint,
            json={"document_type": "resume", "title": "Support resume", "source_url": ""},
        ).status_code
        == 200
    )
    invalid = client.post(
        endpoint,
        json={
            "document_type": "resume",
            "title": "Other resume",
            "source_url": "http://example.test/resume",
        },
    )
    assert invalid.status_code == 422
    assert "public HTTPS URL" in invalid.text
