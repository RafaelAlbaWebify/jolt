from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.orm import Session

from jolt.professional_intelligence_registry import list_configured_professional_sources
from jolt.professional_intelligence_sources import ProfessionalIntelligenceSource


class ProfessionalCaptureExclusion(BaseModel):
    source: ProfessionalIntelligenceSource
    reason: str


class ProfessionalCapturePlan(BaseModel):
    mode: str = "preview_only"
    execution_available: bool = False
    planned_sources: list[ProfessionalIntelligenceSource]
    excluded_sources: list[ProfessionalCaptureExclusion]
    safety_constraints: list[str]


def build_professional_capture_plan(session: Session) -> ProfessionalCapturePlan:
    planned: list[ProfessionalIntelligenceSource] = []
    excluded: list[ProfessionalCaptureExclusion] = []

    for source in list_configured_professional_sources(session):
        if not source.enabled:
            excluded.append(ProfessionalCaptureExclusion(source=source, reason="disabled_by_user"))
        elif not source.initial_scope:
            excluded.append(ProfessionalCaptureExclusion(source=source, reason="deferred_scope"))
        else:
            planned.append(source)

    return ProfessionalCapturePlan(
        planned_sources=planned,
        excluded_sources=excluded,
        safety_constraints=[
            "explicit_user_start_required",
            "supervised_read_only_navigation",
            "approved_registry_urls_only",
            "no_credentials_cookies_or_tokens_in_evidence",
            "no_connect_follow_like_comment_apply_send_or_invitation_actions",
            "no_unattended_capture",
        ],
    )
