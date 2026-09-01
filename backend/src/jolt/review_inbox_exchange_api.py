from __future__ import annotations

from collections.abc import Callable, Iterator
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from jolt.application_outcomes_exchange_api import build_application_outcomes_exchange_router
from jolt.data_quality_exchange_api import build_data_quality_exchange_router
from jolt.errors import JoltNotFoundError
from jolt.linkedin_profile_exchange_api import build_linkedin_profile_exchange_router
from jolt.market_intelligence_exchange_api import build_market_intelligence_exchange_router
from jolt.professional_evidence_exchange_api import build_professional_evidence_exchange_router
from jolt.review_inbox_exchange import build_review_inbox_exchange_json
from jolt.search_preference_exchange_api import build_search_preference_exchange_router
from jolt.skills_preparation_exchange_api import build_skills_preparation_exchange_router

SessionProvider = Callable[[], Iterator[Session]]


def build_review_inbox_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["ai-review", "exports"])
    router.include_router(build_market_intelligence_exchange_router(get_session))
    router.include_router(build_application_outcomes_exchange_router(get_session))
    router.include_router(build_linkedin_profile_exchange_router(get_session))
    router.include_router(build_skills_preparation_exchange_router(get_session))
    router.include_router(build_professional_evidence_exchange_router(get_session))
    router.include_router(build_search_preference_exchange_router(get_session))
    router.include_router(build_data_quality_exchange_router(get_session))
    session_dependency = Depends(get_session)

    @router.get("/api/exports/review-inbox-ai-exchange")
    def review_inbox_ai_exchange(
        session: Session = session_dependency,
    ) -> StreamingResponse:
        try:
            content = build_review_inbox_exchange_json(session)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return StreamingResponse(
            BytesIO(content),
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=JOLT_REVIEW_INBOX_AI_EXCHANGE.json"
            },
        )

    return router
