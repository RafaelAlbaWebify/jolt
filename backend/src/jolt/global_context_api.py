from __future__ import annotations

from fastapi import APIRouter, HTTPException

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.global_context import (
    GlobalAIContextOverlay,
    apply_global_context_patch,
    build_global_context_exchange,
)


def build_global_context_router() -> APIRouter:
    router = APIRouter(prefix="/api/ai-context", tags=["ai-context"])

    @router.get("/export", response_model=AIExchangeInput)
    def export_global_context() -> AIExchangeInput:
        return build_global_context_exchange()

    @router.post("/import", response_model=GlobalAIContextOverlay)
    def import_global_context(output: AIExchangeOutput) -> GlobalAIContextOverlay:
        try:
            return apply_global_context_patch(output)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
