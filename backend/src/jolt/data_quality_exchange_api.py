from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackIndex, list_ai_exchange_feedback
from jolt.data_quality_exchange import (
    DataQualityExchangeImportResponse,
    build_data_quality_exchange,
    import_data_quality_exchange,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_data_quality_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(prefix="/api/ai-data-quality", tags=["data-quality", "ai-exchange"])
    session_dependency = Depends(get_session)

    @router.get("/export", response_model=AIExchangeInput)
    def export_data_quality(
        session: Session = session_dependency,
    ) -> AIExchangeInput:
        return build_data_quality_exchange(session)

    @router.post("/import", response_model=DataQualityExchangeImportResponse)
    def import_data_quality(
        output: AIExchangeOutput,
    ) -> DataQualityExchangeImportResponse:
        try:
            return import_data_quality_exchange(output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/feedback", response_model=AIExchangeFeedbackIndex)
    def data_quality_feedback() -> AIExchangeFeedbackIndex:
        return list_ai_exchange_feedback(section="data_quality")

    return router
