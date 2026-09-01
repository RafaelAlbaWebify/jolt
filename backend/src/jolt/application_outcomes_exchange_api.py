from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackIndex, list_ai_exchange_feedback
from jolt.application_outcomes_exchange import (
    ApplicationOutcomesExchangeImportResponse,
    build_application_outcomes_exchange,
    import_application_outcomes_exchange,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_application_outcomes_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(prefix="/api/ai-applications", tags=["applications", "ai-exchange"])
    session_dependency = Depends(get_session)

    @router.get("/export", response_model=AIExchangeInput)
    def export_application_outcomes(
        session: Session = session_dependency,
    ) -> AIExchangeInput:
        return build_application_outcomes_exchange(session)

    @router.post("/import", response_model=ApplicationOutcomesExchangeImportResponse)
    def import_application_outcomes(
        output: AIExchangeOutput,
    ) -> ApplicationOutcomesExchangeImportResponse:
        try:
            return import_application_outcomes_exchange(output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/feedback", response_model=AIExchangeFeedbackIndex)
    def application_outcome_feedback() -> AIExchangeFeedbackIndex:
        return list_ai_exchange_feedback(section="applications")

    return router
