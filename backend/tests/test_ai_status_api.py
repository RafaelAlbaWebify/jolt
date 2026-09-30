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
