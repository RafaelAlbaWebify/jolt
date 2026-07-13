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
                "Support SQL integrations, APIs, incidents, logs, DNS, and production applications."
            ),
        },
    )
    assert intake.status_code == 200

    response = client.get("/api/opportunities")
    assert response.status_code == 200
    opportunities = response.json()
    assert len(opportunities) == 1

    opportunity = opportunities[0]
    assert opportunity["evaluation_id"] != intake.json()["evaluation_id"]
    assert opportunity["source_url"] == "https://example.test/jobs/123?utm_source=test"
    assert opportunity["confidence"] in {"medium", "high"}
    assert opportunity["ranking_score"] > 0
    assert opportunity["reasons"]
    assert opportunity["strengths"]
    assert opportunity["fit_summary"]
    assert opportunity["profile_version_id"] == "rafael-job-search:v2"
    assert opportunity["engine_version"] == "profile-rules-v2"
    assert opportunity["review_decision"] is None

    readiness = opportunity["readiness"]
    assert readiness["report_id"]
    assert readiness["profile_version_id"] == "rafael-job-search:v2"
    assert readiness["engine_version"] == "application-readiness-v1"
    assert readiness["priority"] in {"low", "medium", "high"}
    assert 0 <= readiness["readiness_score"] <= 100
    assert readiness["evidence_matches"]
    assert readiness["cv_tailoring_points"]
    assert readiness["interview_questions"]
    assert readiness["revision_topics"]
    assert readiness["checklist"]

    second = client.get("/api/opportunities").json()[0]["readiness"]
    assert second["report_id"] == readiness["report_id"]
