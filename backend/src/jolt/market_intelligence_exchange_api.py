from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.market_intelligence import build_market_intelligence
from jolt.market_intelligence_exchange import (
    MarketIntelligenceExchangeImportResponse,
    build_market_intelligence_exchange,
    import_market_intelligence_exchange,
)
from jolt.market_intelligence_view import MarketIntelligenceView, build_market_intelligence_view

SessionProvider = Callable[[], Iterator[Session]]


def build_market_intelligence_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(prefix="/api/ai-market", tags=["market-intelligence", "ai-exchange"])
    session_dependency = Depends(get_session)

    @router.get("/view", response_model=MarketIntelligenceView)
    def market_intelligence_view(
        session: Session = session_dependency,
    ) -> MarketIntelligenceView:
        return build_market_intelligence_view(session)

    @router.get("/automatic")
    def automatic_market_indicators(
        session: Session = session_dependency,
        timeframe: str = "all",
        source_scope: str = "all",
    ) -> dict[str, object]:
        """Calculate local market indicators without any ChatGPT import."""
        if timeframe not in {"all", "last_7_days", "last_30_days"}:
            raise HTTPException(status_code=422, detail="Invalid market timeframe")
        if source_scope not in {"all", "capture_batches", "manual_intake"}:
            raise HTTPException(status_code=422, detail="Invalid market source scope")
        return build_market_intelligence(
            session, timeframe=timeframe, source_scope=source_scope
        )

    @router.get("/export", response_model=AIExchangeInput, deprecated=True)
    def export_market_intelligence(
        session: Session = session_dependency,
    ) -> AIExchangeInput:
        return build_market_intelligence_exchange(session)

    @router.post(
        "/import", deprecated=True, response_model=MarketIntelligenceExchangeImportResponse
    )
    def import_market_intelligence(
        output: AIExchangeOutput,
    ) -> MarketIntelligenceExchangeImportResponse:
        try:
            return import_market_intelligence_exchange(output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
