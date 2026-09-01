from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.ai_exchange_feedback_store import AIExchangeFeedbackIndex, list_ai_exchange_feedback
from jolt.professional_evidence_exchange import (
    ProfessionalEvidenceExchangeImportResponse,
    build_professional_evidence_exchange,
    import_professional_evidence_exchange,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_professional_evidence_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(
        prefix="/api/ai-professional-evidence",
        tags=["professional-intelligence", "ai-exchange"],
    )
    session_dependency = Depends(get_session)

    @router.get("/export", response_model=AIExchangeInput)
    def export_professional_evidence(
        session: Session = session_dependency,
    ) -> AIExchangeInput:
        return build_professional_evidence_exchange(session)

    @router.post("/import", response_model=ProfessionalEvidenceExchangeImportResponse)
    def import_professional_evidence(
        output: AIExchangeOutput,
    ) -> ProfessionalEvidenceExchangeImportResponse:
        try:
            return import_professional_evidence_exchange(output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/feedback", response_model=AIExchangeFeedbackIndex)
    def professional_evidence_feedback() -> AIExchangeFeedbackIndex:
        return list_ai_exchange_feedback(section="professional_evidence")

    return router
