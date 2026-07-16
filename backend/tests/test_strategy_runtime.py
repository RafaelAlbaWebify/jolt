import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from jolt.database import Evaluation, ProfileVersion, create_session_factory
from jolt.main import create_app
from jolt.strategy_runtime import ENGINE_VERSION


def _profile_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "profile_id": "private-test-profile",
        "version": 3,
        "display_name": "Private Candidate Name",
        "role_families": [
            {
                "id": "application_support",
                "label": "Application Support",
                "priority": "primary",
                "terms": ["application support"],
                "strategic_value": 95,
            }
        ],
        "capabilities": [
            {
                "id": "incident_support",
                "label": "Incident support",
                "terms": ["incident"],
                "evidence_level": 5,
                "transferable_to": ["production support"],
                "preparation_topics": [],
            },
            {
                "id": "api_support",
                "label": "API support",
                "terms": ["api"],
                "evidence_level": 2,
                "transferable_to": ["integration"],
                "preparation_topics": ["Practise HTTP troubleshooting."],
            },
        ],
        "eligibility_rules": [],
        "preparation": {
            "hours_per_week": 20,
            "default_days_until_technical": 10,
            "ai_guided_study": True,
            "documentation": True,
            "labs": True,
            "mock_interviews": True,
            "maximum_parallel_processes": 3,
        },
        "weights": {
            "role_alignment": 20,
            "demonstrated_capability": 25,
            "transferable_capability": 10,
            "gap_feasibility": 15,
            "opportunity_quality": 15,
            "strategic_value": 15,
        },
    }


def test_private_strategy_is_persisted_without_profile_contents(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "jolt.db"
    profile_path = tmp_path / "active.private.json"
    profile_path.write_text(json.dumps(_profile_payload()), encoding="utf-8")
    monkeypatch.setenv("JOLT_PROFILE_PATH", str(profile_path))

    client = TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/strategy",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote\n"
                "Own incidents and troubleshoot API integrations in production support."
            ),
        },
    )
    assert intake.status_code == 200

    response = client.get("/api/opportunities")
    assert response.status_code == 200
    opportunity = response.json()[0]
    assert opportunity["engine_version"] == ENGINE_VERSION
    assert opportunity["profile_version_id"] == "private-test-profile:v3"
    assert opportunity["fit_now"] is not None
    assert opportunity["fit_by_interview"] >= opportunity["fit_now"]
    assert opportunity["fit_on_the_job"] >= opportunity["fit_by_interview"]
    assert opportunity["interview_days"] == 10
    assert opportunity["strategy_gaps"][0]["gap_type"] == "preparable_in_1_to_2_weeks"
    assert opportunity["preparation_plan"] == ["Practise HTTP troubleshooting."]

    session_factory = create_session_factory(
        f"sqlite:///{database_path.as_posix()}"
    )
    with session_factory() as session:
        profile = session.get(ProfileVersion, "private-test-profile:v3")
        assert profile is not None
        metadata = json.loads(profile.configuration_json)
        assert metadata["private_configuration_stored"] is False
        assert metadata["profile_sha256"]
        assert "Private Candidate Name" not in profile.configuration_json
        assert "Practise HTTP troubleshooting" not in profile.configuration_json

        evaluations = session.scalars(
            select(Evaluation).where(Evaluation.engine_version == ENGINE_VERSION)
        ).all()
        assert len(evaluations) == 1

    second = client.get("/api/opportunities")
    assert second.status_code == 200
    with session_factory() as session:
        evaluations = session.scalars(
            select(Evaluation).where(Evaluation.engine_version == ENGINE_VERSION)
        ).all()
        assert len(evaluations) == 1


def test_missing_private_profile_preserves_legacy_workbench(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "legacy.db"
    monkeypatch.setenv("JOLT_PROFILE_PATH", str(tmp_path / "missing.private.json"))
    client = TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/legacy",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Support incidents, SQL, APIs, logs, DNS and production applications."
            ),
        },
    )
    assert intake.status_code == 200

    response = client.get("/api/opportunities")
    assert response.status_code == 200
    opportunity = response.json()[0]
    assert opportunity["engine_version"] == "profile-rules-v2"
    assert opportunity["fit_now"] is None
    assert opportunity["strategy_gaps"] == []
