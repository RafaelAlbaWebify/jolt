from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackIndex, list_ai_exchange_feedback
from jolt.skills_preparation_exchange import (
    SkillsPreparationExchangeImportResponse,
    build_skills_preparation_exchange,
    import_skills_preparation_exchange,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_skills_preparation_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(prefix="/api/ai-skills", tags=["skills", "ai-exchange"])
    session_dependency = Depends(get_session)

    @router.get("/export", response_model=AIExchangeInput)
    def export_skills_preparation(
        session: Session = session_dependency,
    ) -> AIExchangeInput:
        return build_skills_preparation_exchange(session)

    @router.post("/import", response_model=SkillsPreparationExchangeImportResponse)
    def import_skills_preparation(
        output: AIExchangeOutput,
    ) -> SkillsPreparationExchangeImportResponse:
        try:
            return import_skills_preparation_exchange(output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/feedback", response_model=AIExchangeFeedbackIndex)
    def skills_preparation_feedback() -> AIExchangeFeedbackIndex:
        return list_ai_exchange_feedback(section="skills_gaps")

    return router
