from __future__ import annotations

from collections.abc import Callable, Iterator
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from jolt.unified_ai_work_package import (
    UnifiedAIUpdate,
    build_unified_ai_work_package_json,
    import_unified_ai_update,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_unified_ai_work_package_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["ai-work-package", "exports"])
    session_dependency = Depends(get_session)

    @router.get("/api/ai-work-package/export")
    def export_ai_work_package(session: Session = session_dependency) -> StreamingResponse:
        content = build_unified_ai_work_package_json(session)
        return StreamingResponse(
            BytesIO(content),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=JOLT_AI_WORK_PACKAGE.json"},
        )

    @router.post("/api/ai-work-package/import")
    def import_ai_work_package(
        payload: UnifiedAIUpdate,
        session: Session = session_dependency,
    ):
        try:
            return import_unified_ai_update(session, payload)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
