from __future__ import annotations

from fastapi.testclient import TestClient

from jolt.application_readiness import READINESS_ENGINE_VERSION, analyze_readiness
from jolt.database import Posting
from jolt.main import create_app


def test_readiness_analysis_contains_evidence_but_no_jolt_ranking() -> None:
    posting = Posting(
        id="posting-1",
        source_document_id="source-1",
        canonical_url="https://example.test/jobs/1",
        identity_key="test-identity",
        title="Application Support Engineer",
        company="Example Systems",
        location="Remote Spain",
        description=(
            "Own production incidents, inspect logs, troubleshoot SQL integrations, "
            "use PowerShell, and document escalation evidence."
        ),
    )

    analysis = analyze_readiness(posting)
    payload = analysis.as_dict()

    assert "priority" not in payload
    assert "readiness_score" not in payload
    assert payload["evidence_matches"]
    assert payload["cv_tailoring_points"]
    assert payload["interview_questions"]
    assert payload["checklist"]


def test_readiness_api_exposes_evidence_not_authoritative_career_judgment(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'readiness-boundary.db').as_posix()}"
    client = TestClient(create_app(database_url))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/support",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Own incidents, inspect logs, troubleshoot SQL integrations, "
                "and document escalation evidence."
            ),
        },
    )
    assert intake.status_code == 200
    posting_id = intake.json()["posting_id"]

    response = client.post(f"/api/opportunities/{posting_id}/readiness/refresh")

    assert response.status_code == 200
    payload = response.json()

    assert payload["engine_version"] == READINESS_ENGINE_VERSION
    assert "priority" not in payload
    assert "readiness_score" not in payload
    assert payload["evidence_matches"]
    assert payload["credibility_warnings"] == []
    assert payload["checklist"]


def test_historical_v1_ranking_fields_are_filtered_from_runtime_payload(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'historical-readiness.db').as_posix()}"
    client = TestClient(create_app(database_url))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/history",
            "raw_text": (
                "Technical Support Engineer\n"
                "Example Company\n"
                "Location: Spain\n"
                "Troubleshoot incidents and maintain support documentation."
            ),
        },
    )
    assert intake.status_code == 200
    posting_id = intake.json()["posting_id"]

    refreshed = client.post(f"/api/opportunities/{posting_id}/readiness/refresh")
    assert refreshed.status_code == 200

    history = client.get(f"/api/opportunities/{posting_id}/readiness/history")
    assert history.status_code == 200

    for report in history.json():
        assert "priority" not in report
        assert "readiness_score" not in report
