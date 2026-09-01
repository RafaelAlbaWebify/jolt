from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackIndex, list_ai_exchange_feedback
from jolt.linkedin_profile_exchange import (
    LinkedInProfileExchangeImportResponse,
    build_linkedin_profile_exchange,
    import_linkedin_profile_exchange,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_linkedin_profile_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(prefix="/api/ai-linkedin", tags=["linkedin-command-center", "ai-exchange"])
    session_dependency = Depends(get_session)

    @router.get("/export", response_model=AIExchangeInput)
    def export_linkedin_profile(
        session: Session = session_dependency,
    ) -> AIExchangeInput:
        return build_linkedin_profile_exchange(session)

    @router.post("/import", response_model=LinkedInProfileExchangeImportResponse)
    def import_linkedin_profile(
        output: AIExchangeOutput,
        session: Session = session_dependency,
    ) -> LinkedInProfileExchangeImportResponse:
        try:
            return import_linkedin_profile_exchange(session, output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/feedback", response_model=AIExchangeFeedbackIndex)
    def linkedin_profile_feedback() -> AIExchangeFeedbackIndex:
        return list_ai_exchange_feedback(section="linkedin_profile")

    return router
