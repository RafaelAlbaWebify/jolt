from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(database: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database.as_posix()}"))


def _application(
    client: TestClient,
    *,
    source_url: str = "https://example.test/jobs/psi?utm_source=linkedin",
    title: str = "IT Infrastructure Engineer (Windows, Active Directory & VMware)",
    company: str = "PSI CRO",
    location: str = "St.-Maur-des-Fossés, Île-de-France, France",
) -> tuple[str, str]:
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": source_url,
            "raw_text": (
                f"{title}\n{company}\nLocation: {location}\n"
                "Windows, Active Directory, VMware and infrastructure support."
            ),
        },
    )
    assert intake.status_code == 200
    row = intake.json()
    review = client.post(
        f"/api/opportunities/{row['posting_id']}/reviews",
        json={"evaluation_id": row["evaluation_id"], "decision": "pursue"},
    )
    assert review.status_code == 200
    pipeline = client.get("/api/application-index").json()
    application = next(item for item in pipeline if item["posting_id"] == row["posting_id"])
    return row["posting_id"], application["application_id"]


def test_edit_location_preserves_application_posting_status_and_history(tmp_path: Path) -> None:
    database = tmp_path / "location.db"
    client = _client(database)
    posting_id, application_id = _application(client)

    before = client.get(f"/api/applications/{application_id}").json()
    response = client.patch(
        f"/api/applications/{application_id}/metadata",
        json={"location": "  Madrid, Spain  "},
    )

    assert response.status_code == 200
    edited = response.json()
    assert edited["application_id"] == application_id
    assert edited["posting_id"] == posting_id
    assert edited["status"] == "preparing"
    assert edited["location"] == "Madrid, Spain"

    after = client.get(f"/api/applications/{application_id}").json()
    assert after["application_id"] == before["application_id"]
    assert after["posting_id"] == before["posting_id"]
    assert after["status"] == before["status"]
    assert [event["event_type"] for event in after["events"]][:-1] == [
        event["event_type"] for event in before["events"]
    ]
    assert after["events"][-1]["event_type"] == "metadata_updated"
    assert "Location:" in after["events"][-1]["notes"]


def test_edit_job_url_canonicalizes_and_recalculates_identity_without_rewriting_source(
    tmp_path: Path,
) -> None:
    database = tmp_path / "url.db"
    client = _client(database)
    posting_id, application_id = _application(client)
    new_url = (
        "https://jobs.smartrecruiters.com/psicro/"
        "744000151009639-it-infrastructure-engineer-windows-active-directory-vmware-"
        "?utm_source=linkedin#apply"
    )

    response = client.patch(
        f"/api/applications/{application_id}/metadata",
        json={"job_url": new_url},
    )

    assert response.status_code == 200
    canonical = (
        "https://jobs.smartrecruiters.com/psicro/"
        "744000151009639-it-infrastructure-engineer-windows-active-directory-vmware-"
    )
    assert response.json()["job_url"] == canonical

    with sqlite3.connect(database) as connection:
        posting = connection.execute(
            "SELECT canonical_url, identity_key, source_document_id FROM postings WHERE id = ?",
            (posting_id,),
        ).fetchone()
        source = connection.execute(
            "SELECT source_url, raw_text FROM source_documents WHERE id = ?",
            (posting[2],),
        ).fetchone()

    assert posting[0] == canonical
    assert posting[1] == f"url:{canonical}"
    assert source[0] == "https://example.test/jobs/psi?utm_source=linkedin"
    assert "St.-Maur-des-Fossés" in source[1]

    pipeline = client.get("/api/application-index").json()
    row = next(item for item in pipeline if item["posting_id"] == posting_id)
    assert row["job_url"] == canonical
    assert row["source_url"] == "https://example.test/jobs/psi?utm_source=linkedin"


def test_duplicate_identity_is_rejected_and_rolls_back_all_metadata_changes(tmp_path: Path) -> None:
    database = tmp_path / "collision.db"
    client = _client(database)
    posting_id, application_id = _application(client)

    duplicate = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/already-owned",
            "raw_text": "Other role\nOther company\nLocation: Spain\nSupport.",
        },
    )
    assert duplicate.status_code == 200

    response = client.patch(
        f"/api/applications/{application_id}/metadata",
        json={
            "location": "Madrid, Spain",
            "job_url": "https://example.test/jobs/already-owned?utm_source=duplicate",
            "notes": "This must not persist.",
        },
    )

    assert response.status_code == 409
    assert "already belongs to another JOLT opportunity" in response.json()["detail"]

    with sqlite3.connect(database) as connection:
        posting = connection.execute(
            "SELECT canonical_url, identity_key, location FROM postings WHERE id = ?",
            (posting_id,),
        ).fetchone()
        application = connection.execute(
            "SELECT notes, status FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        metadata_events = connection.execute(
            "SELECT COUNT(*) FROM application_events WHERE application_id = ? AND event_type = 'metadata_updated'",
            (application_id,),
        ).fetchone()[0]

    assert posting == (
        "https://example.test/jobs/psi",
        "url:https://example.test/jobs/psi",
        "St.-Maur-des-Fossés, Île-de-France, France",
    )
    assert application == ("Created automatically from pursue review decision.", "preparing")
    assert metadata_events == 0


def test_edit_title_company_application_url_and_notes_preserves_resources(tmp_path: Path) -> None:
    database = tmp_path / "fields.db"
    client = _client(database)
    posting_id, application_id = _application(client)

    task = client.post(
        f"/api/applications/{application_id}/tasks",
        json={"title": "Tailor CV", "notes": "Keep me", "due_at": None},
    )
    assert task.status_code == 200
    interview = client.post(
        f"/api/applications/{application_id}/interviews",
        json={
            "interview_type": "technical_interview",
            "scheduled_at": "2026-10-10T10:00:00+02:00",
            "timezone": "Europe/Madrid",
            "format_location": "Teams",
            "participants": "Hiring manager",
            "preparation_notes": "Keep me",
        },
    )
    assert interview.status_code == 200
    contact = client.post(
        f"/api/applications/{application_id}/contacts",
        json={
            "name": "Recruiter",
            "role": "Talent",
            "company": "PSI CRO",
            "email": "",
            "phone": "",
            "linkedin_url": "",
            "notes": "Keep me",
        },
    )
    assert contact.status_code == 200
    document = client.post(
        f"/api/applications/{application_id}/documents",
        json={
            "document_type": "resume",
            "title": "Tailored CV",
            "file_path": "",
            "source_url": "",
            "status": "ready",
            "notes": "Keep me",
        },
    )
    assert document.status_code == 200

    response = client.patch(
        f"/api/applications/{application_id}/metadata",
        json={
            "title": "  IT Infrastructure Engineer  ",
            "company": "  PSI CRO  ",
            "application_url": " https://careers.example.test/apply/123 ",
            "notes": "  Madrid application version  ",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["posting_id"] == posting_id
    assert body["application_id"] == application_id
    assert body["status"] == "preparing"
    assert body["title"] == "IT Infrastructure Engineer"
    assert body["company"] == "PSI CRO"
    assert body["application_url"] == "https://careers.example.test/apply/123"
    assert body["notes"] == "Madrid application version"

    assert len(client.get(f"/api/applications/{application_id}/tasks").json()) == 1
    assert len(client.get(f"/api/applications/{application_id}/interviews").json()) == 1
    assert len(client.get(f"/api/applications/{application_id}/contacts").json()) == 1
    assert len(client.get(f"/api/applications/{application_id}/documents").json()) == 1


def test_invalid_job_url_rolls_back_other_requested_changes(tmp_path: Path) -> None:
    database = tmp_path / "invalid-url.db"
    client = _client(database)
    posting_id, application_id = _application(client)

    response = client.patch(
        f"/api/applications/{application_id}/metadata",
        json={"location": "Madrid, Spain", "job_url": "ftp://example.test/job"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Job posting URL must be a valid http/https URL."

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT location, canonical_url, identity_key FROM postings WHERE id = ?",
            (posting_id,),
        ).fetchone()
    assert row == (
        "St.-Maur-des-Fossés, Île-de-France, France",
        "https://example.test/jobs/psi",
        "url:https://example.test/jobs/psi",
    )


def test_closed_application_outcome_survives_metadata_edit(tmp_path: Path) -> None:
    database = tmp_path / "outcome.db"
    client = _client(database)
    posting_id, application_id = _application(client)

    outcome = client.post(
        f"/api/applications/{application_id}/outcomes",
        json={
            "outcome_type": "rejected_by_employer",
            "notes": "Historical outcome must survive metadata correction.",
        },
    )
    assert outcome.status_code == 200

    edited = client.patch(
        f"/api/applications/{application_id}/metadata",
        json={"company": "PSI CRO Spain", "location": "Madrid, Spain"},
    )
    assert edited.status_code == 200
    assert edited.json()["application_id"] == application_id
    assert edited.json()["posting_id"] == posting_id
    assert edited.json()["status"] == "rejected"

    detail = client.get(f"/api/applications/{application_id}").json()
    assert detail["outcome_type"] == "rejected_by_employer"
    assert detail["status"] == "rejected"
    assert detail["events"][-1]["event_type"] == "metadata_updated"


def test_notes_audit_records_change_without_copying_note_contents(tmp_path: Path) -> None:
    database = tmp_path / "notes-audit.db"
    client = _client(database)
    _, application_id = _application(client)
    private_note = (
        "Long operator note that should remain on the application, not be duplicated in history."
    )

    edited = client.patch(
        f"/api/applications/{application_id}/metadata",
        json={"notes": private_note},
    )
    assert edited.status_code == 200
    assert edited.json()["notes"] == private_note

    detail = client.get(f"/api/applications/{application_id}").json()
    audit = detail["events"][-1]
    assert audit["event_type"] == "metadata_updated"
    assert audit["notes"] == "Notes: updated"
    assert private_note not in audit["notes"]
