from __future__ import annotations

from collections.abc import Callable, Iterator
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from jolt.errors import JoltNotFoundError
from jolt.review_inbox_exchange import build_review_inbox_exchange_json

SessionProvider = Callable[[], Iterator[Session]]


def build_review_inbox_exchange_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["ai-review", "exports"])
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
