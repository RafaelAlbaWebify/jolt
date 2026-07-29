from fastapi.testclient import TestClient

from jolt.main import create_app


def test_archiving_application_hides_it_from_application_index_but_keeps_history(tmp_path) -> None:
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
    history = client.get(f"/api/applications/{application_id}")
    assert history.status_code == 200
    assert history.json()["status"] == "archived"
    assert any(
        event["event_type"] == "application_archived"
        for event in history.json()["events"]
    )
