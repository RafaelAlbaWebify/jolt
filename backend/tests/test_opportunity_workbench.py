from fastapi.testclient import TestClient

from jolt.main import create_app


def test_opportunity_workbench_exposes_evaluation_evidence(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'workbench.db').as_posix()}"
    client = TestClient(create_app(database_url))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/123?utm_source=test",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Support SQL integrations, APIs, incidents, and production applications."
            ),
        },
    )
    assert intake.status_code == 200

    response = client.get("/api/opportunities")
    assert response.status_code == 200
    opportunities = response.json()
    assert len(opportunities) == 1

    opportunity = opportunities[0]
    assert opportunity["evaluation_id"] == intake.json()["evaluation_id"]
    assert opportunity["source_url"] == "https://example.test/jobs/123?utm_source=test"
    assert opportunity["confidence"] == "medium"
    assert opportunity["ranking_score"] > 0
    assert opportunity["reasons"]
    assert opportunity["profile_version_id"] == "default-job-search:v1"
    assert opportunity["engine_version"] == "rules-v1"
    assert opportunity["review_decision"] is None
