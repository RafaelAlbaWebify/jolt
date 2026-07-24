from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.professional_intelligence_records import ProfessionalSourceOverride
from jolt.professional_intelligence_sources import (
    ProfessionalIntelligenceSource,
    professional_intelligence_source_defaults,
    validate_professional_source_url,
)


class ProfessionalSourceUpdateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1)
    initial_scope: bool
    enabled: bool

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Source label is required.")
        return normalized

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        return validate_professional_source_url(value)


def list_configured_professional_sources(session: Session) -> list[ProfessionalIntelligenceSource]:
    defaults = professional_intelligence_source_defaults()
    overrides = {
        item.source_id: item
        for item in session.scalars(select(ProfessionalSourceOverride)).all()
        if item.source_id in defaults
    }
    configured: list[ProfessionalIntelligenceSource] = []
    for source_id, default in defaults.items():
        override = overrides.get(source_id)
        if override is None:
            configured.append(default.model_copy())
            continue
        configured.append(
            default.model_copy(
                update={
                    "label": override.label,
                    "url": override.url,
                    "initial_scope": override.initial_scope,
                    "enabled": override.enabled,
                }
            )
        )
    return configured


def update_professional_source(
    session: Session,
    source_id: str,
    request: ProfessionalSourceUpdateRequest,
) -> ProfessionalIntelligenceSource:
    defaults = professional_intelligence_source_defaults()
    default = defaults.get(source_id)
    if default is None:
        raise LookupError(f"Unknown Professional Intelligence source: {source_id}")

    normalized_url = validate_professional_source_url(request.url)
    for source in list_configured_professional_sources(session):
        if source.source_id != source_id and source.url == normalized_url:
            raise ValueError("Professional Intelligence source URLs must remain unique.")

    override = session.get(ProfessionalSourceOverride, source_id)
    if override is None:
        override = ProfessionalSourceOverride(
            source_id=source_id,
            label=request.label,
            url=normalized_url,
            initial_scope=request.initial_scope,
            enabled=request.enabled,
            updated_at=utc_now(),
        )
        session.add(override)
    else:
        override.label = request.label
        override.url = normalized_url
        override.initial_scope = request.initial_scope
        override.enabled = request.enabled
        override.updated_at = utc_now()
    session.commit()

    return default.model_copy(
        update={
            "label": override.label,
            "url": override.url,
            "initial_scope": override.initial_scope,
            "enabled": override.enabled,
        }
    )


def reset_professional_source(session: Session, source_id: str) -> ProfessionalIntelligenceSource:
    defaults = professional_intelligence_source_defaults()
    default = defaults.get(source_id)
    if default is None:
        raise LookupError(f"Unknown Professional Intelligence source: {source_id}")

    override = session.get(ProfessionalSourceOverride, source_id)
    if override is not None:
        session.delete(override)
        session.commit()
    return default.model_copy()
