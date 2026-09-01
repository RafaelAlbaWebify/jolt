from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from jolt.database import create_session_factory
from jolt.market_intelligence_exchange_api import build_market_intelligence_exchange_router


def _client(tmp_path) -> TestClient:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")

    def get_session() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(build_market_intelligence_exchange_router(get_session))
    return TestClient(app)


def test_market_exchange_export_has_empty_evidence_on_fresh_database(tmp_path) -> None:
    response = _client(tmp_path).get("/api/ai-market/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_type"] == "jolt_ai_exchange_input"
    assert payload["scope"]["section"] == "market_insights"
    assert payload["evidence"]["counts"] == {"jobs": 0, "capture_runs": 0}


def test_market_exchange_import_rejects_wrong_scope(tmp_path) -> None:
    response = _client(tmp_path).post(
        "/api/ai-market/import",
        json={
            "contract_type": "jolt_ai_exchange_output",
            "contract_version": "1.0",
            "exchange_id": "wrong-scope",
            "reviewed_at": "2026-09-01T12:00:00+00:00",
            "review_source": "chatgpt",
            "review_version": "market-v1",
            "scope": {"section": "review_inbox", "analysis_types": ["context_update"]},
            "feedback": [],
            "context_patch": {},
            "summary": {},
        },
    )

    assert response.status_code == 400
    assert "scope.section=market_insights" in response.json()["detail"]
