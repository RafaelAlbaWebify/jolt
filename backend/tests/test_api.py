from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(database_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))


def test_manual_intake_review_duplicate_and_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "jolt.db"
    client = _client(database_path)
    payload = {
        "source_url": "https://example.com/jobs/123?utm_source=test",
        "raw_text": (
            "Application Support Engineer\n"
            "Example Systems\n"
            "Location: Remote Spain\n"
            "Provide application support, SQL troubleshooting, incident ownership, "
            "and API analysis."
        ),
    }

    intake = client.post("/api/intake/manual", json=payload)
    assert intake.status_code == 200
    result = intake.json()
    assert result["identity_status"] == "new"
    assert result["title"] == "Application Support Engineer"
    assert result["company"] == "Example Systems"
    assert result["location"] == "Remote Spain"
    assert result["recommendation"] == "pursue"
    assert result["profile_version_id"] == "default-job-search:v1"
    assert result["engine_version"] == "rules-v1"

    review = client.post(
        f"/api/opportunities/{result['posting_id']}/reviews",
        json={
            "evaluation_id": result["evaluation_id"],
            "decision": "pursue",
            "reason_code": "strong_alignment",
            "notes": "Prepare a tailored application.",
        },
    )
    assert review.status_code == 200
    assert review.json()["evaluation_overridden"] is False

    duplicate = client.post("/api/intake/manual", json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["identity_status"] == "confirmed_duplicate"
    assert duplicate.json()["posting_id"] == result["posting_id"]
    assert duplicate.json()["source_document_id"] != result["source_document_id"]

    restarted_client = _client(database_path)
    compact = restarted_client.get("/api/opportunity-index")
    assert compact.status_code == 200
    compact_items = compact.json()
    assert len(compact_items) == 1
    compact_opportunity = compact_items[0]
    assert compact_opportunity == {
        "posting_id": result["posting_id"],
        "evaluation_id": compact_opportunity["evaluation_id"],
        "source_url": "https://example.com/jobs/123",
        "title": "Application Support Engineer",
        "company": "Example Systems",
        "location": "Remote Spain",
        "recommendation": "pursue",
        "confidence": compact_opportunity["confidence"],
        "ranking_score": compact_opportunity["ranking_score"],
        "review_decision": "pursue",
        "application_id": None,
        "application_status": None,
        "outcome_type": None,
    }
    assert "readiness" not in compact_opportunity
    assert "strengths" not in compact_opportunity
    assert "preparation_plan" not in compact_opportunity

    opportunities = restarted_client.get("/api/opportunities")
    assert opportunities.status_code == 200
    items = opportunities.json()
    assert len(items) == 1
    opportunity = items[0]
    assert opportunity["posting_id"] == result["posting_id"]
    assert opportunity["title"] == "Application Support Engineer"
    assert opportunity["company"] == "Example Systems"
    assert opportunity["recommendation"] == "pursue"
    assert opportunity["proposed_decision"] in {"pursue", "consider"}
    assert opportunity["ranking_score"] >= 50
    assert opportunity["review_decision"] == "pursue"
    assert opportunity["profile_version_id"] == "rafael-job-search:v2"
    assert opportunity["engine_version"] == "profile-rules-v2"
    assert opportunity["strengths"]
    assert opportunity["fit_summary"]
    assert "application_support" in opportunity["dimensions"]


def test_missing_information_does_not_become_hard_reject(tmp_path: Path) -> None:
    client = _client(tmp_path / "uncertain.db")
    response = client.post(
        "/api/intake/manual",
        json={"raw_text": "Support Engineer\nUnknown Company\nGeneral troubleshooting role."},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["recommendation"] == "consider"
    assert result["confidence"] in {"low", "medium"}
    assert result["identity_status"] == "new"


def test_automated_review_rejects_verified_language_blocker(tmp_path: Path) -> None:
    client = _client(tmp_path / "blocker.db")
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.com/jobs/german",
            "raw_text": (
                "Technical Support Engineer\nExample GmbH\nLocation: Remote Europe\n"
                "Troubleshoot incidents and APIs. Must speak German."
            ),
        },
    )
    assert intake.status_code == 200

    opportunities = client.get("/api/opportunities")
    assert opportunities.status_code == 200
    opportunity = opportunities.json()[0]
    assert opportunity["recommendation"] == "reject"
    assert opportunity["proposed_decision"] == "reject"
    assert opportunity["confidence"] == "high"
    assert opportunity["blockers"]
