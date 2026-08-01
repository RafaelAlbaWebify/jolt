from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def test_market_uses_latest_fallback_evaluation_and_excludes_audit_fixture(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    client.post(
        "/api/intake/manual",
        json={
            "source_type": "manual",
            "source_url": "https://example.test/real-role",
            "raw_text": (
                "Technical Support Engineer\nReal Company\n"
                "Location: Remote Spain\nSQL API incident support"
            ),
        },
    )
    client.post(
        "/api/intake/manual",
        json={
            "source_type": "manual",
            "source_url": "https://example.test/audit-role",
            "raw_text": (
                "JOLT Daily Workflow Audit 123\nAudit Systems\n"
                "Location: Remote Spain\nSQL API support"
            ),
        },
    )

    payload = client.get("/api/market-intelligence?timeframe=all&source_scope=manual_intake").json()

    assert payload["total_unique_roles"] == 1
    assert payload["excluded_synthetic_count"] == 1
    assert payload["evaluation_coverage"]["evaluated_count"] == 1
    assert payload["evaluation_coverage"]["fallback_engine_count"] == 1
    assert sum(item["count"] for item in payload["all"]["fit_distribution"]) == 1


def test_shift_is_blocked_only_when_saved_preferences_exclude_it(monkeypatch) -> None:
    from jolt import preference_aware_evaluation
    from jolt.job_search_preferences import JobSearchPreferences

    monkeypatch.setattr(
        preference_aware_evaluation,
        "load_job_search_preferences",
        lambda: JobSearchPreferences(excluded_shifts=[]),
    )
    recommendation, _, score, reasons = preference_aware_evaluation.evaluate_text_with_preferences(
        "Technical Support Engineer night shifts SQL API incident"
    )
    assert recommendation == "pursue"
    assert score > 0
    assert not any("shift excluded" in reason for reason in reasons)

    monkeypatch.setattr(
        preference_aware_evaluation,
        "load_job_search_preferences",
        lambda: JobSearchPreferences(excluded_shifts=["night"]),
    )
    recommendation, _, score, reasons = preference_aware_evaluation.evaluate_text_with_preferences(
        "Technical Support Engineer night shifts SQL API incident"
    )
    assert recommendation == "reject"
    assert score == 0
    assert any("shift excluded" in reason for reason in reasons)


def test_required_language_uses_current_saved_language_preferences(monkeypatch) -> None:
    from jolt import preference_aware_evaluation
    from jolt.job_search_preferences import JobSearchPreferences

    monkeypatch.setattr(
        preference_aware_evaluation,
        "load_job_search_preferences",
        lambda: JobSearchPreferences(languages=["Spanish", "English"]),
    )
    recommendation, _, score, reasons = preference_aware_evaluation.evaluate_text_with_preferences(
        "French-speaking Technical Support Engineer SQL API incident"
    )
    assert recommendation == "reject"
    assert score == 0
    assert any("required language" in reason for reason in reasons)

    monkeypatch.setattr(
        preference_aware_evaluation,
        "load_job_search_preferences",
        lambda: JobSearchPreferences(languages=["Spanish", "English", "French"]),
    )
    recommendation, _, score, reasons = preference_aware_evaluation.evaluate_text_with_preferences(
        "French-speaking Technical Support Engineer SQL API incident"
    )
    assert recommendation == "pursue"
    assert score > 0
    assert not any("required language" in reason for reason in reasons)
