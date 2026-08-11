from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path, name: str) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / name).as_posix()}"))


def _create_application(client: TestClient) -> tuple[str, str]:
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/pipeline-coherence",
            "raw_text": (
                "Application Support Engineer\nExample Systems\nLocation: Remote Spain\n"
                "Application support, SQL, incident ownership, API troubleshooting and integration work."
            ),
        },
    )
    assert intake.status_code == 200
    opportunity = intake.json()
    review = client.post(
        f"/api/opportunities/{opportunity['posting_id']}/reviews",
        json={
            "evaluation_id": opportunity["evaluation_id"],
            "decision": "pursue",
            "notes": "Create the durable application record.",
        },
    )
    assert review.status_code == 200
    application_index = client.get("/api/application-index")
    assert application_index.status_code == 200
    row = next(
        item for item in application_index.json() if item["posting_id"] == opportunity["posting_id"]
    )
    assert row["application_id"]
    assert row["application_status"] == "preparing"
    return opportunity["posting_id"], row["application_id"]


def test_application_index_does_not_resurrect_deleted_pursued_posting(tmp_path) -> None:
    client = _client(tmp_path, "delete-index.db")
    posting_id, application_id = _create_application(client)

    submitted = client.post(
        f"/api/applications/{application_id}/transitions",
        json={"status": "submitted", "notes": "Submitted externally."},
    )
    assert submitted.status_code == 200
    closed = client.post(
        f"/api/applications/{application_id}/outcomes",
        json={
            "outcome_type": "rejected_by_employer",
            "notes": "Employer rejected the application.",
        },
    )
    assert closed.status_code == 200
    deleted = client.post(f"/api/applications/{application_id}/delete")
    assert deleted.status_code == 200

    application_index = client.get("/api/application-index")
    assert application_index.status_code == 200
    assert all(item["posting_id"] != posting_id for item in application_index.json())

    preserved = client.get("/api/opportunity-index?include_reviewed=true")
    assert preserved.status_code == 200
    preserved_row = next(item for item in preserved.json() if item["posting_id"] == posting_id)
    assert preserved_row["review_decision"] == "pursue"
    assert preserved_row["application_id"] is None


def test_archived_application_resources_are_read_only_until_restore(tmp_path) -> None:
    client = _client(tmp_path, "archived-read-only.db")
    _, application_id = _create_application(client)

    task = client.post(
        f"/api/applications/{application_id}/tasks",
        json={"title": "Follow up", "notes": "Before archive.", "due_at": None},
    )
    assert task.status_code == 200
    task_id = task.json()["task_id"]

    interview_payload = {
        "interview_type": "technical_interview",
        "scheduled_at": "2026-08-20T10:00:00+02:00",
        "timezone": "Europe/Madrid",
        "format_location": "Teams",
        "participants": "Recruiter",
        "preparation_notes": "Prepare examples.",
    }
    interview = client.post(
        f"/api/applications/{application_id}/interviews",
        json=interview_payload,
    )
    assert interview.status_code == 200
    interview_id = interview.json()["interview_id"]

    contact_payload = {
        "name": "Morgan Lee",
        "role": "Recruiter",
        "company": "Example Systems",
        "email": "morgan@example.test",
        "phone": "",
        "linkedin_url": "",
        "notes": "Before archive.",
    }
    contact = client.post(
        f"/api/applications/{application_id}/contacts",
        json=contact_payload,
    )
    assert contact.status_code == 200
    contact_id = contact.json()["contact_id"]

    document_payload = {
        "document_type": "resume",
        "title": "Submitted resume",
        "file_path": "C:/resume.pdf",
        "source_url": "",
        "status": "submitted",
        "notes": "Before archive.",
    }
    document = client.post(
        f"/api/applications/{application_id}/documents",
        json=document_payload,
    )
    assert document.status_code == 200
    document_id = document.json()["document_id"]

    archived = client.post(
        f"/api/applications/{application_id}/archive",
        json={"notes": "Archive for read-only test."},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    for suffix in ("tasks", "interviews", "contacts", "documents"):
        response = client.get(f"/api/applications/{application_id}/{suffix}")
        assert response.status_code == 200
        assert len(response.json()) == 1

    rejected_writes = [
        client.post(
            f"/api/applications/{application_id}/tasks",
            json={"title": "Blocked task", "notes": "", "due_at": None},
        ),
        client.post(
            f"/api/application-tasks/{task_id}/update",
            json={"title": "Changed task", "notes": "", "due_at": None},
        ),
        client.post(f"/api/application-tasks/{task_id}/complete"),
        client.post(
            f"/api/applications/{application_id}/interviews",
            json=interview_payload,
        ),
        client.post(
            f"/api/application-interviews/{interview_id}/update",
            json={**interview_payload, "outcome_notes": "Blocked."},
        ),
        client.post(
            f"/api/application-interviews/{interview_id}/complete",
            json={"outcome_notes": "Blocked."},
        ),
        client.post(
            f"/api/application-interviews/{interview_id}/cancel",
            json={"outcome_notes": "Blocked."},
        ),
        client.post(
            f"/api/applications/{application_id}/contacts",
            json={**contact_payload, "name": "Blocked contact"},
        ),
        client.post(
            f"/api/application-contacts/{contact_id}/update",
            json={**contact_payload, "role": "Blocked change"},
        ),
        client.post(
            f"/api/applications/{application_id}/documents",
            json={**document_payload, "title": "Blocked document"},
        ),
        client.post(
            f"/api/application-documents/{document_id}/update",
            json={**document_payload, "notes": "Blocked change"},
        ),
    ]

    for response in rejected_writes:
        assert response.status_code == 409
        assert response.json()["detail"] == (
            "Archived applications are read-only. Restore the application before making changes."
        )

    restored = client.post(
        f"/api/applications/{application_id}/restore",
        json={"notes": "Restore after read-only test."},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "preparing"

    allowed = client.post(
        f"/api/applications/{application_id}/tasks",
        json={"title": "Allowed after restore", "notes": "", "due_at": None},
    )
    assert allowed.status_code == 200


def test_runtime_registers_one_application_archive_post_route(tmp_path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'routes.db').as_posix()}")
    archive_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/applications/{application_id}/archive"
        and "POST" in route.methods
    ]
    assert len(archive_routes) == 1
