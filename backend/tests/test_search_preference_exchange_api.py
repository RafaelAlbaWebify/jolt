from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from jolt.ai_exchange_feedback_store import AIExchangeFeedbackIndex
from jolt.database import create_session_factory
from jolt.search_preference_exchange_api import build_search_preference_exchange_router


def _client(tmp_path, monkeypatch) -> TestClient:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")
    monkeypatch.setattr(
        "jolt.search_preference_exchange_api.list_ai_exchange_feedback",
        lambda section=None: AIExchangeFeedbackIndex(total_import_count=0),
    )

    def get_session() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(build_search_preference_exchange_router(get_session))
    return TestClient(app)


def test_search_preference_export_is_empty_on_fresh_database(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).get("/api/ai-search-preferences/export")
    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["section"] == "search_preferences"
    assert payload["evidence"]["counts"] == {"postings": 0, "capture_runs": 0}
    assert "job_search_preferences" in payload["protected_state"]["non_patchable"]


def test_search_preference_feedback_endpoint_is_read_only(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).get("/api/ai-search-preferences/feedback")
    assert response.status_code == 200
    assert response.json() == {"total_import_count": 0, "records": []}


def test_search_preference_import_rejects_wrong_scope(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).post(
        "/api/ai-search-preferences/import",
        json={
            "contract_type": "jolt_ai_exchange_output",
            "contract_version": "1.0",
            "exchange_id": "wrong-scope",
            "reviewed_at": "2026-09-01T12:00:00+00:00",
            "review_source": "chatgpt",
            "review_version": "search-v1",
            "scope": {"section": "market_insights", "analysis_types": ["context_update"]},
            "feedback": [],
            "context_patch": {},
            "summary": {},
        },
    )
    assert response.status_code == 400
    assert "scope.section=search_preferences" in response.json()["detail"]
