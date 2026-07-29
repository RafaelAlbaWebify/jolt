from fastapi.testclient import TestClient

from jolt.main import create_app


def test_archiving_and_restoring_application_card_keeps_history(tmp_path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.com/jobs/support-engineer",
            "raw_text": "Support Engineer\nExample Co\nLocation: Spain Remote\nApplication support SQL incident API integration work.",
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
            "notes": "Good enough to prepare.",
        },
    )
    assert review.status_code == 200

    application = client.post(
        f"/api/opportunities/{opportunity['posting_id']}/applications",
        json={
            "application_url": "https://example.com/apply",
            "resume_used": "Rafael_CV.pdf",
            "notes": "Prepare first.",
        },
    )
    assert application.status_code == 200
    application_id = application.json()["application_id"]
    assert len(client.get("/api/application-index").json()) == 1

    archived = client.post(
        f"/api/applications/{application_id}/archive",
        json={"notes": "Not relevant anymore."},
    )
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert archived.json()["status"] == "archived"

    assert client.get("/api/application-index").json() == []
    archived_index = client.get("/api/application-index?include_archived=true")
    assert archived_index.status_code == 200
    assert archived_index.json()[0]["application_status"] == "archived"

    history = client.get(f"/api/applications/{application_id}")
    assert history.status_code == 200
    assert history.json()["status"] == "archived"
    assert any(event["event_type"] == "application_archived" for event in history.json()["events"])

    restored = client.post(
        f"/api/applications/{application_id}/restore",
        json={"notes": "Relevant again."},
    )
    assert restored.status_code == 200
    assert restored.json()["archived"] is False
    assert restored.json()["status"] == "preparing"

    active_index = client.get("/api/application-index")
    assert active_index.status_code == 200
    assert active_index.json()[0]["application_status"] == "preparing"

    restored_history = client.get(f"/api/applications/{application_id}").json()
    assert any(
        event["event_type"] == "application_restored"
        for event in restored_history["events"]
    )
