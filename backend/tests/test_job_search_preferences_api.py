from pathlib import Path

from fastapi.testclient import TestClient

from jolt import job_search_preferences as preferences_module
from jolt.evaluation_strategy import (
    CapabilityEvidence,
    RoleFamily,
    StrategyProfile,
)
from jolt.main import create_app


def _client(database_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))


def _redirect_preferences(
    monkeypatch,
    path: Path,
) -> None:
    monkeypatch.setattr(
        preferences_module,
        "_data_path",
        lambda: path,
    )


def _strategy_profile() -> StrategyProfile:
    return StrategyProfile(
        profile_id="preferences-api-test",
        version=1,
        role_families=[
            RoleFamily(
                id="support",
                label="Support",
                priority="primary",
                terms=[
                    "support engineer",
                    "technical support",
                ],
                strategic_value=90,
            )
        ],
        capabilities=[
            CapabilityEvidence(
                id="support",
                label="Support",
                terms=[
                    "technical support",
                    "troubleshooting",
                    "incident",
                    "api",
                ],
                evidence_level=5,
            )
        ],
    )


def _install_strategy_profile(
    monkeypatch,
) -> None:
    profile = _strategy_profile()

    # The refresh endpoint imports the loader into jolt.main.
    monkeypatch.setattr(
        "jolt.main.load_active_strategy_profile",
        lambda: profile,
    )

    # Opportunity detail independently reconstructs the current
    # StrategyAssessment through its own imported loader.
    monkeypatch.setattr(
        "jolt.opportunity_workbench.load_active_strategy_profile",
        lambda: profile,
    )


def test_job_search_preferences_api_persists_atomically(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preferences_path = tmp_path / "settings" / "job_search_preferences.json"

    _redirect_preferences(
        monkeypatch,
        preferences_path,
    )

    client = _client(tmp_path / "preferences.db")

    initial = client.get("/api/job-search-preferences")

    assert initial.status_code == 200
    assert initial.json()["base_locality"] == "Vigo, Galicia, Spain"

    # A read must not create persistence directories.
    assert not preferences_path.parent.exists()

    payload = initial.json()
    payload["max_hybrid_distance_km"] = 45
    payload["languages"] = [
        "Spanish",
        "English",
        "German",
    ]
    payload["expected_salary_eur_target"] = 50000

    saved = client.post(
        "/api/job-search-preferences",
        json=payload,
    )

    assert saved.status_code == 200
    assert saved.json()["max_hybrid_distance_km"] == 45

    assert preferences_path.exists()
    assert not Path(str(preferences_path) + ".tmp").exists()

    restarted = _client(tmp_path / "preferences.db")

    loaded = restarted.get("/api/job-search-preferences")

    assert loaded.status_code == 200
    assert loaded.json() == saved.json()

    invalid = {
        **saved.json(),
        "max_hybrid_distance_km": 501,
    }

    rejected = restarted.post(
        "/api/job-search-preferences",
        json=invalid,
    )

    assert rejected.status_code == 422

    unchanged = restarted.get("/api/job-search-preferences")

    assert unchanged.json() == saved.json()


def test_saved_preferences_change_next_evaluation_refresh(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preferences_path = tmp_path / "settings" / "job_search_preferences.json"

    _redirect_preferences(
        monkeypatch,
        preferences_path,
    )

    _install_strategy_profile(
        monkeypatch,
    )

    client = _client(tmp_path / "evaluation-refresh.db")

    preferences = client.get("/api/job-search-preferences").json()

    preferences["excluded_keywords"] = [
        *preferences["excluded_keywords"],
        "quantumwidget",
    ]

    saved = client.post(
        "/api/job-search-preferences",
        json=preferences,
    )

    assert saved.status_code == 200

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": ("https://example.com/jobs/preference-refresh"),
            "raw_text": (
                "Technical Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Provide technical support, "
                "troubleshooting, incident ownership, "
                "API analysis and quantumwidget operations."
            ),
        },
    )

    assert intake.status_code == 200

    posting_id = intake.json()["posting_id"]

    first_refresh = client.post("/api/evaluations/refresh")

    assert first_refresh.status_code == 200

    first_refresh_payload = first_refresh.json()

    assert first_refresh_payload["authoritative_engine"] == "profile-rules-v10"

    assert first_refresh_payload["strategy_evaluation_count"] == 1

    before = client.get(f"/api/opportunity-detail/{posting_id}")

    assert before.status_code == 200

    before_payload = before.json()

    assert before_payload["engine_version"] == "profile-rules-v10"

    assert before_payload["recommendation"] == "do_not_pursue"

    assert any(
        "excluded keyword: quantumwidget" in blocker.casefold()
        for blocker in before_payload["blockers"]
    )

    preferences = client.get("/api/job-search-preferences").json()

    preferences["excluded_keywords"] = [
        keyword
        for keyword in preferences["excluded_keywords"]
        if keyword.casefold() != "quantumwidget"
    ]

    saved = client.post(
        "/api/job-search-preferences",
        json=preferences,
    )

    assert saved.status_code == 200

    second_refresh = client.post("/api/evaluations/refresh")

    assert second_refresh.status_code == 200

    second_refresh_payload = second_refresh.json()

    assert second_refresh_payload["authoritative_engine"] == "profile-rules-v10"

    assert second_refresh_payload["strategy_evaluation_count"] == 1

    after = client.get(f"/api/opportunity-detail/{posting_id}")

    assert after.status_code == 200

    after_payload = after.json()

    assert after_payload["engine_version"] == "profile-rules-v10"

    assert not any(
        "excluded keyword: quantumwidget" in blocker.casefold()
        for blocker in after_payload["blockers"]
    )

    assert after_payload["recommendation"] != "do_not_pursue"
