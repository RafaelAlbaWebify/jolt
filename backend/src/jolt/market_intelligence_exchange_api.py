from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.market_intelligence_exchange import (
    MarketIntelligenceExchangeImportResponse,
    build_market_intelligence_exchange,
    import_market_intelligence_exchange,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_market_intelligence_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(prefix="/api/ai-market", tags=["market-intelligence", "ai-exchange"])
    session_dependency = Depends(get_session)

    @router.get("/export", response_model=AIExchangeInput)
    def export_market_intelligence(
        session: Session = session_dependency,
    ) -> AIExchangeInput:
        return build_market_intelligence_exchange(session)

    @router.post("/import", response_model=MarketIntelligenceExchangeImportResponse)
    def import_market_intelligence(
        output: AIExchangeOutput,
    ) -> MarketIntelligenceExchangeImportResponse:
        try:
            return import_market_intelligence_exchange(output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
