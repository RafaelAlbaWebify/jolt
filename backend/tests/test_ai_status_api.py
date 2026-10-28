from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_ai_status_is_backend_derived_on_empty_database(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    response = client.get("/api/ai-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] == "no_evidence"
    assert payload["attention_sections"] == 0
    assert payload["sections"]["review_inbox"]["state"] == "no_evidence"
    assert payload["sections"]["market_insights"]["state"] == "no_evidence"
    assert payload["sections"]["applications"]["state"] == "no_evidence"
    assert payload["sections"]["linkedin_profile"]["state"] == "no_evidence"
    assert payload["sections"]["search_strategy"]["state"] == "no_evidence"
    assert payload["sections"]["data_quality"]["operator_relevant"] is False


def test_professional_evidence_freshness_does_not_depend_on_linkedin_capture(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime
    from unittest.mock import patch

    from jolt.ai_status import build_ai_status
    from jolt.database import create_session_factory

    session = create_session_factory(f"sqlite:///{(tmp_path / 'separate.db').as_posix()}")()
    try:
        with patch("jolt.ai_status._latest_linkedin_evidence_at", return_value=datetime.now(UTC)):
            result = build_ai_status(session)
        assert result.sections["linkedin_profile"].state == "not_analyzed"
        assert result.sections["professional_evidence"].state == "no_evidence"
    finally:
        session.close()
