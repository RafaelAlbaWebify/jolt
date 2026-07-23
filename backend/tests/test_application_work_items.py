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


def test_tasks_persist_complete_reopen_and_append_timeline_events(tmp_path: Path) -> None:
    database = tmp_path / "tasks.db"
    client = _client(database)
    application = _application(client)
    application_id = application["application_id"]

    created = client.post(
        f"/api/applications/{application_id}/tasks",
        json={
            "title": "Tailor SQL troubleshooting evidence",
            "notes": "Use the Infios and factory-support examples.",
            "due_at": "2026-07-25T17:00:00+02:00",
        },
    )
    assert created.status_code == 200
    task = created.json()
    assert task["status"] == "open"
    assert task["title"] == "Tailor SQL troubleshooting evidence"

    completed = client.post(f"/api/application-tasks/{task['task_id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    reopened = client.post(f"/api/application-tasks/{task['task_id']}/reopen")
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"
    assert reopened.json()["completed_at"] is None

    restarted = _client(database)
    tasks = restarted.get(f"/api/applications/{application_id}/tasks")
    assert tasks.status_code == 200
    assert len(tasks.json()) == 1
    assert tasks.json()[0]["status"] == "open"

    timeline = restarted.get(f"/api/applications/{application_id}").json()["events"]
    assert [event["event_type"] for event in timeline[-3:]] == [
        "task_created",
        "task_completed",
        "task_reopened",
    ]


def test_interviews_persist_update_complete_and_append_timeline_events(tmp_path: Path) -> None:
    database = tmp_path / "interviews.db"
    client = _client(database)
    application = _application(client)
    application_id = application["application_id"]

    created = client.post(
        f"/api/applications/{application_id}/interviews",
        json={
            "interview_type": "technical_interview",
            "scheduled_at": "2026-07-28T10:30:00+02:00",
            "timezone": "Europe/Madrid",
            "format_location": "Google Meet",
            "participants": "Hiring manager, senior support engineer",
            "preparation_notes": "Review SQL, logs, APIs, and escalation evidence.",
        },
    )
    assert created.status_code == 200
    interview = created.json()
    assert interview["status"] == "scheduled"

    updated = client.post(
        f"/api/application-interviews/{interview['interview_id']}/update",
        json={
            "interview_type": "technical_interview",
            "scheduled_at": "2026-07-29T11:00:00+02:00",
            "timezone": "Europe/Madrid",
            "format_location": "Microsoft Teams",
            "participants": "Hiring manager, senior support engineer",
            "preparation_notes": "Add a concise API troubleshooting example.",
            "outcome_notes": "",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["format_location"] == "Microsoft Teams"

    completed = client.post(
        f"/api/application-interviews/{interview['interview_id']}/complete",
        json={"outcome_notes": "Strong discussion; awaiting hiring-manager feedback."},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    restarted = _client(database)
    interviews = restarted.get(f"/api/applications/{application_id}/interviews")
    assert interviews.status_code == 200
    assert len(interviews.json()) == 1
    assert interviews.json()[0]["status"] == "completed"

    timeline = restarted.get(f"/api/applications/{application_id}").json()["events"]
    assert [event["event_type"] for event in timeline[-3:]] == [
        "interview_created",
        "interview_updated",
        "interview_completed",
    ]


def test_work_item_routes_return_not_found_for_unknown_application(tmp_path: Path) -> None:
    client = _client(tmp_path / "missing.db")
    assert client.get("/api/applications/missing/tasks").status_code == 404
    assert client.get("/api/applications/missing/interviews").status_code == 404
