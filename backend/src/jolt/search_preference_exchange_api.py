from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackIndex, list_ai_exchange_feedback
from jolt.search_preference_exchange import (
    SearchPreferenceExchangeImportResponse,
    build_search_preference_exchange,
    import_search_preference_exchange,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_search_preference_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(prefix="/api/ai-search-preferences", tags=["search", "ai-exchange"])
    session_dependency = Depends(get_session)

    @router.get("/export", response_model=AIExchangeInput)
    def export_search_preferences(
        session: Session = session_dependency,
    ) -> AIExchangeInput:
        return build_search_preference_exchange(session)

    @router.post("/import", response_model=SearchPreferenceExchangeImportResponse)
    def import_search_preferences(
        output: AIExchangeOutput,
    ) -> SearchPreferenceExchangeImportResponse:
        try:
            return import_search_preference_exchange(output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/feedback", response_model=AIExchangeFeedbackIndex)
    def search_preference_feedback() -> AIExchangeFeedbackIndex:
        return list_ai_exchange_feedback(section="search_preferences")

    return router
