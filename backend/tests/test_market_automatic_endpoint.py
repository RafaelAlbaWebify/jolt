from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import jolt.market_intelligence_exchange_api as market_api


def _client(monkeypatch) -> TestClient:
    def session_provider() -> Iterator[Session]:
        yield None  # type: ignore[misc]

    monkeypatch.setattr(
        market_api,
        "build_market_intelligence",
        lambda session, *, timeframe, source_scope: {
            "total_unique_roles": 12,
            "timeframe": timeframe,
            "source_scope": source_scope,
        },
    )
    app = FastAPI()
    app.include_router(market_api.build_market_intelligence_exchange_router(session_provider))
    return TestClient(app)


def test_automatic_market_endpoint_reads_local_indicators(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.get("/api/ai-market/automatic")
    assert response.status_code == 200
    assert response.json()["total_unique_roles"] == 12
    assert response.json()["source_scope"] == "all"


def test_automatic_market_endpoint_rejects_invalid_filters(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.get("/api/ai-market/automatic?timeframe=invalid")
    assert response.status_code == 422
