from __future__ import annotations

from fastapi import APIRouter, HTTPException

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.global_context import GlobalAIContextOverlay, build_global_context_exchange


def build_global_context_router() -> APIRouter:
    router = APIRouter(prefix="/api/ai-context", tags=["ai-context"])

    @router.get("/export", response_model=AIExchangeInput, deprecated=True)
    def export_global_context() -> AIExchangeInput:
        return build_global_context_exchange()

    @router.post("/import", response_model=GlobalAIContextOverlay, deprecated=True)
    def import_global_context(output: AIExchangeOutput) -> GlobalAIContextOverlay:
        del output
        raise HTTPException(
            status_code=409,
            detail=(
                "Direct global AI context imports are deprecated. "
                "Use /api/ai-work-package/import so all durable AI strategy changes "
                "are validated and applied atomically."
            ),
        )

    return router
