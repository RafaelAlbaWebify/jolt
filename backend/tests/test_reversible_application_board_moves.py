from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(database_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))


def _create_application(client: TestClient) -> str:
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.com/jobs/reversible-board",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Application support, SQL, incident ownership, API analysis, and integration troubleshooting."
            ),
        },
    )
    assert intake.status_code == 200
    intake_payload = intake.json()

    review = client.post(
        f"/api/opportunities/{intake_payload['posting_id']}/reviews",
        json={
            "evaluation_id": intake_payload["evaluation_id"],
            "decision": "pursue",
            "reason_code": "strong_alignment",
            "notes": "Create an application record.",
        },
    )
    assert review.status_code == 200

    application = client.post(
        f"/api/opportunities/{intake_payload['posting_id']}/applications",
        json={"application_url": "", "resume_used": "", "notes": "Prepared locally."},
    )
    assert application.status_code == 200
    return application.json()["application_id"]


def test_active_stage_corrections_move_forward_and_backward(tmp_path: Path) -> None:
    client = _client(tmp_path / "reversible.db")
    application_id = _create_application(client)

    submitted = client.post(
        f"/api/applications/{application_id}/transitions",
        json={"status": "submitted", "notes": "Submitted externally."},
    )
    assert submitted.status_code == 200

    corrected_forward = client.post(
        f"/api/applications/{application_id}/transitions",
        json={"status": "offer", "notes": "Corrected to offer after missed updates."},
    )
    assert corrected_forward.status_code == 200
    assert corrected_forward.json()["status"] == "offer"
    assert corrected_forward.json()["events"][-1]["event_type"] == "status_corrected"

    corrected_backward = client.post(
        f"/api/applications/{application_id}/transitions",
        json={"status": "submitted", "notes": "Moved back after correcting a board mistake."},
    )
    assert corrected_backward.status_code == 200
    payload = corrected_backward.json()
    assert payload["status"] == "submitted"
    assert payload["outcome_type"] is None
    assert payload["events"][-1]["event_type"] == "status_corrected"
    assert payload["events"][-1]["from_status"] == "offer"
    assert payload["events"][-1]["to_status"] == "submitted"


def test_reopening_clears_current_outcome_but_preserves_history(tmp_path: Path) -> None:
    client = _client(tmp_path / "reopen.db")
    application_id = _create_application(client)

    submitted = client.post(
        f"/api/applications/{application_id}/transitions",
        json={"status": "submitted", "notes": "Submitted externally."},
    )
    assert submitted.status_code == 200

    outcome = client.post(
        f"/api/applications/{application_id}/outcomes",
        json={
            "outcome_type": "rejected_by_employer",
            "reason_code": "role_closed",
            "notes": "Employer initially rejected the application.",
        },
    )
    assert outcome.status_code == 200
    assert outcome.json()["outcome_type"] == "rejected_by_employer"

    reopened = client.post(
        f"/api/applications/{application_id}/transitions",
        json={"status": "recruiter_screen", "notes": "Employer reopened the process."},
    )
    assert reopened.status_code == 200
    payload = reopened.json()
    assert payload["status"] == "recruiter_screen"
    assert payload["outcome_type"] is None

    event_types = [event["event_type"] for event in payload["events"]]
    assert "outcome_recorded" in event_types
    assert event_types[-1] == "application_reopened"
    assert payload["events"][-1]["from_status"] == "rejected"
    assert payload["events"][-1]["to_status"] == "recruiter_screen"
