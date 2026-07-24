from fastapi import APIRouter

from jolt.professional_intelligence_sources import (
    ProfessionalIntelligenceSource,
    list_professional_intelligence_sources,
)


def build_professional_intelligence_router() -> APIRouter:
    router = APIRouter(tags=["professional-intelligence"])

    @router.get(
        "/api/professional-intelligence/sources",
        response_model=list[ProfessionalIntelligenceSource],
    )
    def professional_intelligence_sources() -> list[ProfessionalIntelligenceSource]:
        return list_professional_intelligence_sources()

    return router
