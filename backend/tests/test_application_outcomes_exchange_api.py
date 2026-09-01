from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from jolt.application_outcomes_exchange_api import build_application_outcomes_exchange_router
from jolt.database import create_session_factory


def _client(tmp_path, monkeypatch) -> TestClient:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")
    monkeypatch.setattr(
        "jolt.application_outcomes_exchange_api.list_ai_exchange_feedback",
        lambda section=None: __import__(
            "jolt.ai_exchange_feedback_store", fromlist=["AIExchangeFeedbackIndex"]
        ).AIExchangeFeedbackIndex(total_import_count=0),
    )

    def get_session() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(build_application_outcomes_exchange_router(get_session))
    return TestClient(app)


def test_application_exchange_export_is_empty_on_fresh_database(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).get("/api/ai-applications/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["section"] == "applications"
    assert payload["evidence"]["counts"] == {
        "applications": 0,
        "with_outcomes": 0,
        "active_or_open": 0,
    }


def test_application_exchange_feedback_endpoint_is_read_only(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).get("/api/ai-applications/feedback")

    assert response.status_code == 200
    assert response.json() == {"total_import_count": 0, "records": []}


def test_application_exchange_import_rejects_wrong_scope(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).post(
        "/api/ai-applications/import",
        json={
            "contract_type": "jolt_ai_exchange_output",
            "contract_version": "1.0",
            "exchange_id": "wrong-scope",
            "reviewed_at": "2026-09-01T12:00:00+00:00",
            "review_source": "chatgpt",
            "review_version": "applications-v1",
            "scope": {"section": "market_insights", "analysis_types": ["context_update"]},
            "feedback": [],
            "context_patch": {},
            "summary": {},
        },
    )

    assert response.status_code == 400
    assert "scope.section=applications" in response.json()["detail"]
