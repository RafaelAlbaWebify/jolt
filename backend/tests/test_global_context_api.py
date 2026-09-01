from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jolt.global_context import GlobalAIContextOverlay
from jolt.global_context_api import build_global_context_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(build_global_context_router())
    return TestClient(app)


def test_global_context_export_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.global_context.load_global_ai_context",
        lambda: GlobalAIContextOverlay(market_summary={"sample": True}),
    )

    response = _client().get("/api/ai-context/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_type"] == "jolt_ai_exchange_input"
    assert payload["scope"]["section"] == "global_context"
    assert payload["context"]["ai_context"]["market_summary"] == {"sample": True}


def test_global_context_import_rejects_non_patchable_namespace() -> None:
    response = _client().post(
        "/api/ai-context/import",
        json={
            "contract_type": "jolt_ai_exchange_output",
            "contract_version": "1.0",
            "exchange_id": "exchange-api-test",
            "reviewed_at": datetime.now(UTC).isoformat(),
            "review_source": "chatgpt",
            "review_version": "chatgpt-api-test",
            "scope": {
                "section": "global_context",
                "analysis_types": ["context_update"],
            },
            "feedback": [],
            "context_patch": {
                "job_search_preferences": {"languages": ["German"]}
            },
            "summary": {},
        },
    )

    assert response.status_code == 400
    assert "non-patchable" in response.json()["detail"]
