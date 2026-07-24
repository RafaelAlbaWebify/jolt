from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_application_index_handles_sqlite_naive_due_dates(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'timezone.db').as_posix()}"))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/timezone-regression",
            "raw_text": (
                "Timezone Regression Application\nExample Systems\nLocation: Remote Spain\n"
                "Application support, SQL, APIs, logs, and incident ownership."
            ),
        },
    ).json()
    client.post(
        f"/api/opportunities/{intake['posting_id']}/reviews",
        json={"evaluation_id": intake["evaluation_id"], "decision": "pursue"},
    )
    application = client.post(
        f"/api/opportunities/{intake['posting_id']}/applications",
        json={"notes": "Timezone comparison regression."},
    ).json()
    client.post(
        f"/api/applications/{application['application_id']}/tasks",
        json={
            "title": "Past due task",
            "due_at": "2020-01-01T09:00:00+01:00",
            "notes": "SQLite loads this timestamp without tzinfo.",
        },
    )

    response = client.get("/api/application-index")

    assert response.status_code == 200
    indexed = next(item for item in response.json() if item["posting_id"] == intake["posting_id"])
    assert indexed["next_due_kind"] == "task"
    assert indexed["next_due_at"].endswith("+00:00")
    assert indexed["overdue"] is True
