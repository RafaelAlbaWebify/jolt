from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{path.as_posix()}"))


def test_pursue_creates_preparing_application_in_same_workflow(tmp_path: Path) -> None:
    client = _client(tmp_path / "pursue.db")

    intake = client.post(
        "/api/intake/manual",
        json={
            "raw_text": (
                "Global IT Asset & Service Desk Specialist\n"
                "Fever\n"
                "Location: Madrid\n"
                "Technical support, application support, incident ownership and IT operations."
            )
        },
    ).json()

    reviewed = client.post(
        f"/api/opportunities/{intake['posting_id']}/reviews",
        json={
            "evaluation_id": intake["evaluation_id"],
            "decision": "pursue",
        },
    )

    assert reviewed.status_code == 200

    opportunities = client.get("/api/opportunities").json()
    opportunity = next(item for item in opportunities if item["posting_id"] == intake["posting_id"])

    assert opportunity["review_decision"] == "pursue"
    assert opportunity["application_id"]
    assert opportunity["application_status"] == "preparing"

    application = client.get(f"/api/applications/{opportunity['application_id']}")

    assert application.status_code == 200
    payload = application.json()
    assert payload["status"] == "preparing"
    assert [event["event_type"] for event in payload["events"]] == ["application_created"]


def test_non_pursue_review_does_not_create_application(tmp_path: Path) -> None:
    client = _client(tmp_path / "consider.db")

    intake = client.post(
        "/api/intake/manual",
        json={
            "raw_text": (
                "Support Engineer\nExample Company\nLocation: Madrid\nGeneral technical support."
            )
        },
    ).json()

    reviewed = client.post(
        f"/api/opportunities/{intake['posting_id']}/reviews",
        json={
            "evaluation_id": intake["evaluation_id"],
            "decision": "consider",
        },
    )

    assert reviewed.status_code == 200

    opportunities = client.get("/api/opportunities").json()
    opportunity = next(item for item in opportunities if item["posting_id"] == intake["posting_id"])

    assert opportunity["review_decision"] == "consider"
    assert opportunity["application_id"] is None
    assert opportunity["application_status"] is None
