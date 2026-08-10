from fastapi.testclient import TestClient

from jolt.main import create_app


def _create_application(client: TestClient) -> str:
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.com/jobs/pipeline-cleanup",
            "raw_text": (
                "Support Engineer\n"
                "Example Co\n"
                "Location: Spain Remote\n"
                "Application support SQL incident API integration work."
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
            "reason_code": "fit",
            "notes": "Prepare application.",
        },
    )
    assert review.status_code == 200

    application_index = client.get("/api/application-index")
    assert application_index.status_code == 200

    return application_index.json()[0]["application_id"]


def test_active_application_cannot_be_permanently_deleted(tmp_path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'active.db').as_posix()}"))
    application_id = _create_application(client)

    response = client.post(
        f"/api/applications/{application_id}/delete",
    )

    assert response.status_code == 409
    assert "closed, terminal, or archived" in response.json()["detail"]

    application = client.get(
        f"/api/applications/{application_id}",
    )
    assert application.status_code == 200


def test_terminal_application_can_be_permanently_deleted_without_archive(
    tmp_path,
) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'terminal.db').as_posix()}"))
    application_id = _create_application(client)

    submitted = client.post(
        f"/api/applications/{application_id}/transitions",
        json={
            "status": "submitted",
            "notes": "Submitted externally.",
        },
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
    assert closed.json()["status"] == "rejected"
    assert closed.json()["outcome_type"] == "rejected_by_employer"

    deleted = client.post(
        f"/api/applications/{application_id}/delete",
    )

    assert deleted.status_code == 200
    payload = deleted.json()

    assert payload["deleted"] is True
    assert payload["deleted_outcome_count"] == 1
    assert payload["deleted_event_count"] >= 1

    application = client.get(
        f"/api/applications/{application_id}",
    )
    assert application.status_code == 404

    opportunity_index = client.get(
        "/api/opportunity-index?include_reviewed=true",
    )
    assert opportunity_index.status_code == 200
    assert len(opportunity_index.json()) == 1
