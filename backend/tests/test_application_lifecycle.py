from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{path.as_posix()}"))


def test_pursued_opportunity_becomes_application_with_history_and_outcome(tmp_path: Path) -> None:
    client = _client(tmp_path / "jolt.db")
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
        json={"resume_used": "application-support-v1.pdf", "notes": "Tailor SQL evidence."},
    )
    assert created.status_code == 200
    application = created.json()
    assert application["status"] == "preparing"
    assert [event["to_status"] for event in application["events"]] == ["preparing"]

    submitted = client.post(
        f"/api/applications/{application['application_id']}/transitions",
        json={"status": "submitted", "notes": "Submitted through employer portal."},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    screened = client.post(
        f"/api/applications/{application['application_id']}/transitions",
        json={"status": "recruiter_screen", "notes": "Recruiter call booked."},
    )
    assert screened.status_code == 200

    invalid = client.post(
        f"/api/applications/{application['application_id']}/transitions",
        json={"status": "offer"},
    )
    assert invalid.status_code == 409

    outcome = client.post(
        f"/api/applications/{application['application_id']}/outcomes",
        json={
            "outcome_type": "rejected_by_employer",
            "reason_code": "experience_gap",
            "notes": "Employer wanted deeper product-support experience.",
        },
    )
    assert outcome.status_code == 200
    result = outcome.json()
    assert result["status"] == "rejected"
    assert result["outcome_type"] == "rejected_by_employer"
    assert [event["event_type"] for event in result["events"]] == [
        "application_created",
        "status_changed",
        "status_changed",
        "outcome_recorded",
    ]

    restarted = _client(tmp_path / "jolt.db")
    queue = restarted.get("/api/opportunities").json()
    assert queue[0]["application_status"] == "rejected"
    assert queue[0]["outcome_type"] == "rejected_by_employer"


def test_application_requires_pursue_decision(tmp_path: Path) -> None:
    client = _client(tmp_path / "guard.db")
    intake = client.post(
        "/api/intake/manual",
        json={"raw_text": "Support Engineer\nExample Systems\nGeneral troubleshooting."},
    ).json()
    response = client.post(
        f"/api/opportunities/{intake['posting_id']}/applications",
        json={},
    )
    assert response.status_code == 409
