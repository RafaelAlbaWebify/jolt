from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from jolt.ai_exchange_feedback_store import AIExchangeFeedbackIndex
from jolt.database import create_session_factory
from jolt.skills_preparation_exchange_api import build_skills_preparation_exchange_router


def _client(tmp_path, monkeypatch) -> TestClient:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")
    monkeypatch.setattr(
        "jolt.skills_preparation_exchange_api.list_ai_exchange_feedback",
        lambda section=None: AIExchangeFeedbackIndex(total_import_count=0),
    )

    def get_session() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(build_skills_preparation_exchange_router(get_session))
    return TestClient(app)


def test_skills_exchange_export_is_empty_on_fresh_database(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).get("/api/ai-skills/export")
    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["section"] == "skills_gaps"
    assert payload["evidence"]["counts"] == {"vacancies": 0, "profile_captures": 0}


def test_skills_exchange_feedback_endpoint_is_read_only(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).get("/api/ai-skills/feedback")
    assert response.status_code == 200
    assert response.json() == {"total_import_count": 0, "records": []}


def test_skills_exchange_import_rejects_wrong_scope(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).post(
        "/api/ai-skills/import",
        json={
            "contract_type": "jolt_ai_exchange_output",
            "contract_version": "1.0",
            "exchange_id": "wrong-scope",
            "reviewed_at": "2026-09-01T12:00:00+00:00",
            "review_source": "chatgpt",
            "review_version": "skills-v1",
            "scope": {"section": "market_insights", "analysis_types": ["context_update"]},
            "feedback": [],
            "context_patch": {},
            "summary": {},
        },
    )
    assert response.status_code == 400
    assert "scope.section=skills_gaps" in response.json()["detail"]
