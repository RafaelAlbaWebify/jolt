from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def test_market_exposes_evidence_based_learning_signals(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/intake/manual",
        json={
            "source_type": "manual",
            "source_url": "https://example.test/learning-signal",
            "raw_text": (
                "Technical Support Engineer\n"
                "Signal Systems\n"
                "Location: Remote Spain\n"
                "Requirements: PowerShell and Active Directory are required. "
                "Azure is preferred. Support incidents and automation."
            ),
        },
    )
    assert response.status_code == 200

    payload = client.get("/api/market-intelligence?timeframe=all&source_scope=manual_intake").json()

    assert payload["learning_refresh"]["baseline_label"] == ("Market Baseline v1 — 16 Aug 2026")
    assert "10 new relevant jobs or 7 days" in payload["learning_refresh"]["policy"]

    signals = payload["target"]["learning_signals"]
    by_skill = {item["skill"]: item for item in signals}

    assert "Powershell" in by_skill
    assert by_skill["Powershell"]["demand"] == 1
    assert by_skill["Powershell"]["required_count"] == 1
    assert by_skill["Powershell"]["role_family_count"] >= 1
    assert 0 <= by_skill["Powershell"]["evidence_priority_indicator"] <= 10
    assert by_skill["Powershell"]["preparation_hours"] is None

    explanation = payload["target"]["learning_signal_explanation"]
    assert "not a career prescription" in explanation
    assert "not an attributed per-skill penalty" in explanation
