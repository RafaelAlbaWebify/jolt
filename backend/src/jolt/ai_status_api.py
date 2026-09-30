from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from jolt.ai_status import AIStatusResponse, build_ai_status

SessionProvider = Callable[[], Iterator[Session]]


def build_ai_status_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["ai-status"])
    session_dependency = Depends(get_session)

    @router.get("/api/ai-status", response_model=AIStatusResponse)
    def ai_status(session: Session = session_dependency) -> AIStatusResponse:
        return build_ai_status(session)

    return router
