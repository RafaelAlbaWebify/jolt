from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import LinkedInPresenceCapture
from jolt.global_context import load_global_ai_context

_MAX_PROFILE_SOURCES = 20
_PROFILE_CATEGORIES = frozenset({"profile", "public_profile"})
_EVIDENCE_REF_PREFIX = "linkedin_capture:"

CandidateEvidenceLevel = Literal[
    "professional",
    "project_lab",
    "certification",
    "education",
    "language",
    "explicit_non_claim",
    "unknown",
]


class CandidateEvidenceClaim(BaseModel):
    claim: str = Field(min_length=1, max_length=240)
    evidence_level: CandidateEvidenceLevel
    evidence_summary: str = Field(default="", max_length=2000)
    evidence_refs: list[str] = Field(min_length=1, max_length=20)


class CandidateEvidenceSummary(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    as_of: str = ""
    claims: list[CandidateEvidenceClaim] = Field(default_factory=list, max_length=250)
    notes: list[str] = Field(default_factory=list, max_length=50)


def validate_candidate_evidence_summary(value: dict[str, Any]) -> dict[str, Any]:
    """Validate the AI-owned claim ledger without deciding claim semantics locally."""

    return CandidateEvidenceSummary.model_validate(value).model_dump(mode="json")


def validate_candidate_evidence_refs(session: Session, value: dict[str, Any]) -> None:
    """Require candidate-claim references to resolve to profile evidence in JOLT."""

    summary = CandidateEvidenceSummary.model_validate(value)
    refs = {evidence_ref for claim in summary.claims for evidence_ref in claim.evidence_refs}
    for evidence_ref in refs:
        if not evidence_ref.startswith(_EVIDENCE_REF_PREFIX):
            raise ValueError(f"Unsupported candidate evidence reference: {evidence_ref}")
        capture_id = evidence_ref.removeprefix(_EVIDENCE_REF_PREFIX)
        capture = session.get(LinkedInPresenceCapture, capture_id)
        if capture is None:
            raise ValueError(f"Candidate evidence reference was not found: {evidence_ref}")
        if capture.category not in _PROFILE_CATEGORIES:
            raise ValueError(
                "Candidate evidence reference is not profile evidence: " + evidence_ref
            )


def _source_ref(capture: LinkedInPresenceCapture) -> str:
    return f"{_EVIDENCE_REF_PREFIX}{capture.id}"


def build_candidate_evidence_ledger(session: Session) -> dict[str, Any]:
    """Build deterministic candidate evidence without inferring experience level.

    Captures are selected newest-first and deduplicated by source/category/content so the
    unified package can carry enough raw evidence for ChatGPT to reason about claims
    without asking local Python to classify skills or upgrade mentions into experience.
    """

    captures = session.scalars(
        select(LinkedInPresenceCapture)
        .where(LinkedInPresenceCapture.category.in_(sorted(_PROFILE_CATEGORIES)))
        .order_by(LinkedInPresenceCapture.captured_at.desc(), LinkedInPresenceCapture.id)
    ).all()

    selected: list[LinkedInPresenceCapture] = []
    seen: set[tuple[str, str, str]] = set()
    for capture in captures:
        key = (
            capture.category.strip().casefold(),
            capture.source_url.strip(),
            capture.content_hash,
        )
        if key in seen:
            continue
        seen.add(key)
        selected.append(capture)
        if len(selected) >= _MAX_PROFILE_SOURCES:
            break

    source_evidence = [
        {
            "evidence_ref": _source_ref(capture),
            "capture_id": capture.id,
            "category": capture.category,
            "title": capture.title,
            "source_url": capture.source_url,
            "content_hash": capture.content_hash,
            "captured_at": capture.captured_at.isoformat(),
            "changed_since_previous": capture.changed_since_previous,
            "visible_text": capture.visible_text,
        }
        for capture in selected
    ]

    reviewed_summary = load_global_ai_context().candidate_evidence_summary
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_evidence": source_evidence,
        "reviewed_summary": reviewed_summary,
        "counts": {
            "available_profile_captures": len(captures),
            "exported_profile_sources": len(source_evidence),
            "source_limit": _MAX_PROFILE_SOURCES,
        },
        "authority_notes": {
            "source_evidence": (
                "Deterministically selected raw LinkedIn/profile captures with provenance. "
                "Presence of a term does not prove professional depth or duration."
            ),
            "reviewed_summary": (
                "ChatGPT-derived, user-reviewable claim classification. It may classify evidence "
                "as professional, project_lab, certification, education, language, "
                "explicit_non_claim, or unknown, but must cite evidence_refs."
            ),
            "credibility": (
                "Never upgrade study, certification, lab, project, adjacent exposure, or a simple "
                "mention into unsupported professional production experience."
            ),
        },
    }
