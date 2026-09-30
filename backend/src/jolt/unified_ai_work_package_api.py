from __future__ import annotations

from collections.abc import Callable, Iterator
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from jolt.errors import JoltNotFoundError

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
    def export_ai_work_package(
        discovery_batch_id: str | None = None,
        session: Session = session_dependency,
    ) -> StreamingResponse:
        try:
            content = build_unified_ai_work_package_json(
                session,
                discovery_batch_id=discovery_batch_id,
            )
        except (ValueError, JoltNotFoundError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        filename = (
            f"JOLT_DISCOVERY_BATCH_{discovery_batch_id}_AI_WORK_PACKAGE.json"
            if discovery_batch_id
            else "JOLT_AI_WORK_PACKAGE.json"
        )
        return StreamingResponse(
            BytesIO(content),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
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
