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


def test_task_correction_persists_normalized_values_and_before_after_audit(tmp_path: Path) -> None:
    database = tmp_path / "task-corrections.db"
    client = _client(database)
    application_id = _application(client)["application_id"]

    created = client.post(
        f"/api/applications/{application_id}/tasks",
        json={
            "title": "  Prepare SQL example  ",
            "notes": "  First notes  ",
            "due_at": "2026-07-28T10:00:00+02:00",
        },
    ).json()
    assert created["title"] == "Prepare SQL example"
    assert created["notes"] == "First notes"

    updated = client.post(
        f"/api/application-tasks/{created['task_id']}/update",
        json={
            "title": "  Prepare API example  ",
            "notes": "  Revised notes  ",
            "due_at": "2026-07-29T11:30:00+02:00",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Prepare API example"
    assert updated.json()["notes"] == "Revised notes"

    restarted = _client(database)
    persisted = restarted.get(f"/api/applications/{application_id}/tasks").json()[0]
    assert persisted["title"] == "Prepare API example"
    assert persisted["notes"] == "Revised notes"

    events = restarted.get(f"/api/applications/{application_id}").json()["events"]
    correction = next(event for event in events if event["event_type"] == "task_updated")
    assert "Prepare SQL example" in correction["notes"]
    assert "Prepare API example" in correction["notes"]
    assert "First notes" in correction["notes"]
    assert "Revised notes" in correction["notes"]
    assert "due_at:" in correction["notes"]


def test_interview_correction_persists_normalized_values_and_before_after_audit(
    tmp_path: Path,
) -> None:
    database = tmp_path / "interview-corrections.db"
    client = _client(database)
    application_id = _application(client)["application_id"]

    created = client.post(
        f"/api/applications/{application_id}/interviews",
        json={
            "interview_type": "recruiter_screen",
            "scheduled_at": "2026-07-28T10:00:00+02:00",
            "timezone": "  Europe/Madrid  ",
            "format_location": "  Teams  ",
            "participants": "  Recruiter  ",
            "preparation_notes": "  Initial preparation  ",
        },
    ).json()
    assert created["timezone"] == "Europe/Madrid"
    assert created["format_location"] == "Teams"

    updated = client.post(
        f"/api/application-interviews/{created['interview_id']}/update",
        json={
            "interview_type": "technical_interview",
            "scheduled_at": "2026-07-29T11:30:00+02:00",
            "timezone": "  Europe/Lisbon  ",
            "format_location": "  Office  ",
            "participants": "  Hiring manager  ",
            "preparation_notes": "  Revised preparation  ",
            "outcome_notes": "  Awaiting decision  ",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["timezone"] == "Europe/Lisbon"
    assert updated.json()["outcome_notes"] == "Awaiting decision"

    restarted = _client(database)
    persisted = restarted.get(f"/api/applications/{application_id}/interviews").json()[0]
    assert persisted["interview_type"] == "technical_interview"
    assert persisted["format_location"] == "Office"
    assert persisted["outcome_notes"] == "Awaiting decision"

    events = restarted.get(f"/api/applications/{application_id}").json()["events"]
    correction = next(event for event in events if event["event_type"] == "interview_updated")
    assert "recruiter_screen" in correction["notes"]
    assert "technical_interview" in correction["notes"]
    assert "Teams" in correction["notes"]
    assert "Office" in correction["notes"]
    assert "Initial preparation" in correction["notes"]
    assert "Revised preparation" in correction["notes"]
    assert "Awaiting decision" in correction["notes"]


def test_work_item_text_limits_are_enforced(tmp_path: Path) -> None:
    client = _client(tmp_path / "limits.db")
    application_id = _application(client)["application_id"]

    task = client.post(
        f"/api/applications/{application_id}/tasks",
        json={"title": "Valid", "notes": "x" * 4001, "due_at": None},
    )
    assert task.status_code == 422

    interview = client.post(
        f"/api/applications/{application_id}/interviews",
        json={
            "interview_type": "recruiter_screen",
            "scheduled_at": "2026-07-28T10:00:00+02:00",
            "timezone": "Europe/Madrid",
            "format_location": "x" * 1001,
            "participants": "Recruiter",
            "preparation_notes": "Prepare",
        },
    )
    assert interview.status_code == 422
