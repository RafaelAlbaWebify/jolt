from __future__ import annotations

from collections.abc import Callable, Iterator
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from jolt.errors import JoltNotFoundError
from jolt.market_strategy_package import build_market_strategy_package_json
from jolt.official_source_capture import capture_official_candidates
from jolt.unified_ai_work_package import (
    UnifiedAIUpdate,
    build_review_only_work_package_json,
    build_unified_ai_work_package,
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

    @router.get("/api/ai-work-package/review-export")
    def export_review_only(
        session: Session = session_dependency,
    ) -> StreamingResponse:
        """Review-only package with the existing unified import contract."""
        try:
            content = build_review_only_work_package_json(session)
        except (ValueError, JoltNotFoundError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return StreamingResponse(
            BytesIO(content),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=JOLT_REVIEW_ONLY.json"},
        )

    @router.get("/api/ai-work-package/market-export")
    def export_market_strategy(
        session: Session = session_dependency,
    ) -> StreamingResponse:
        """Strategic market aggregates only; Review Inbox remains separate."""
        content = build_market_strategy_package_json(session)
        return StreamingResponse(
            BytesIO(content),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=JOLT_MARKET_STRATEGY.json"},
        )

    @router.post("/api/ai-work-package/official-evidence/refresh")
    def refresh_official_evidence(
        discovery_batch_id: str | None = None,
        max_jobs: int = 10,
        session: Session = session_dependency,
    ) -> dict[str, object]:
        """Operator-initiated, bounded source gathering before Export AI."""
        try:
            package = build_unified_ai_work_package(session, discovery_batch_id=discovery_batch_id)
            return capture_official_candidates(session, package.review_inbox, max_jobs=max_jobs)
        except (ValueError, JoltNotFoundError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
