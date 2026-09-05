from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import LinkedInPresenceCapture
from jolt.global_context import load_global_ai_context

_MAX_PROFILE_SOURCES = 20
_PROFILE_CATEGORIES = frozenset({"profile", "public_profile"})
_EVIDENCE_REF_PREFIX = "linkedin_capture:"
_PROFILE_COMPLETENESS_PARTIAL_MARKER = "jolt profile section completeness: partial"
_LOGIN_URL_MARKERS = (
    "/login",
    "/checkpoint",
    "/uas/login",
    "authwall",
    "sessionredirect=",
)
_LOGIN_TEXT_MARKERS = (
    "join linkedin",
    "already on linkedin? sign in",
    "email or phone",
    "security verification",
    "verify your identity",
    "let's do a quick security check",
)

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


def _canonical_profile_section_key(capture: LinkedInPresenceCapture) -> tuple[str, str]:
    """Return the stable current-section identity used for candidate evidence selection.

    Historical captures remain in JOLT for provenance, but the AI candidate surface should not
    spend its bounded source budget on repeated old snapshots of the same LinkedIn section.
    Query strings and fragments are deliberately ignored because LinkedIn can vary them without
    changing the underlying Profile / Experience / Skills / Certifications section.
    """

    candidate = capture.source_url.strip()
    if candidate:
        parts = urlsplit(candidate)
        path = parts.path.rstrip("/") + "/"
        canonical_url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))
    else:
        canonical_url = ""
    return capture.category.strip().casefold(), canonical_url.casefold()


def profile_capture_quality_issue(capture: LinkedInPresenceCapture) -> str | None:
    """Return a deterministic reason when a profile capture is not usable evidence.

    LinkedIn login/authwall/checkpoint and explicitly partial profile-section captures are retained
    for audit, but must never be promoted into candidate evidence or AI profile analysis as if they
    were complete profile content.
    """

    source_url = capture.source_url.strip().casefold()
    visible_text = capture.visible_text.strip().casefold()
    notes = capture.notes.strip().casefold()

    if any(marker in source_url for marker in _LOGIN_URL_MARKERS):
        return "linkedin_login_or_authwall_url"
    if any(marker in visible_text for marker in _LOGIN_TEXT_MARKERS):
        return "linkedin_login_or_authwall_text"
    if not visible_text:
        return "empty_profile_capture"
    if _PROFILE_COMPLETENESS_PARTIAL_MARKER in notes:
        return "partial_linkedin_profile_section"
    return None


def validate_candidate_evidence_refs(session: Session, value: dict[str, Any]) -> None:
    """Require candidate-claim references to resolve to usable profile evidence in JOLT."""

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
        quality_issue = profile_capture_quality_issue(capture)
        if quality_issue is not None:
            raise ValueError(
                "Candidate evidence reference points to unusable profile evidence: "
                f"{evidence_ref} ({quality_issue})"
            )


def _source_ref(capture: LinkedInPresenceCapture) -> str:
    return f"{_EVIDENCE_REF_PREFIX}{capture.id}"


def build_candidate_evidence_ledger(session: Session) -> dict[str, Any]:
    """Build deterministic candidate evidence without inferring experience level.

    The newest usable capture for each canonical LinkedIn profile section is authoritative for the
    bounded AI surface. Older snapshots remain stored for provenance/history but no longer crowd
    current Profile, Experience, Skills, Certifications, Recommendations, etc. out of the package.
    Invalid authwall/checkpoint/empty/explicitly-partial captures are excluded.
    """

    captures = session.scalars(
        select(LinkedInPresenceCapture)
        .where(LinkedInPresenceCapture.category.in_(sorted(_PROFILE_CATEGORIES)))
        .order_by(LinkedInPresenceCapture.captured_at.desc(), LinkedInPresenceCapture.id)
    ).all()

    selected: list[LinkedInPresenceCapture] = []
    rejected: list[dict[str, str]] = []
    historical: list[dict[str, str]] = []
    seen_sections: set[tuple[str, str]] = set()

    for capture in captures:
        quality_issue = profile_capture_quality_issue(capture)
        if quality_issue is not None:
            rejected.append(
                {
                    "capture_id": capture.id,
                    "title": capture.title,
                    "category": capture.category,
                    "captured_at": capture.captured_at.isoformat(),
                    "reason": quality_issue,
                }
            )
            continue

        section_key = _canonical_profile_section_key(capture)
        if section_key in seen_sections:
            historical.append(
                {
                    "capture_id": capture.id,
                    "title": capture.title,
                    "category": capture.category,
                    "captured_at": capture.captured_at.isoformat(),
                    "reason": "superseded_profile_section_snapshot",
                }
            )
            continue

        seen_sections.add(section_key)
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
    usable_count = len(captures) - len(rejected)
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_evidence": source_evidence,
        "reviewed_summary": reviewed_summary,
        "counts": {
            "available_profile_captures": len(captures),
            "usable_profile_captures": usable_count,
            "invalid_profile_captures": len(rejected),
            "historical_profile_captures_not_exported": len(historical),
            "exported_profile_sources": len(source_evidence),
            "source_limit": _MAX_PROFILE_SOURCES,
        },
        "excluded_profile_captures": rejected,
        "historical_profile_captures": historical,
        "authority_notes": {
            "source_evidence": (
                "Newest usable capture per canonical LinkedIn profile section, with provenance. "
                "Presence of a term does not prove professional depth or duration."
            ),
            "excluded_profile_captures": (
                "LinkedIn login/authwall/checkpoint, empty, or explicitly partial section captures "
                "are retained for audit but are not candidate evidence."
            ),
            "historical_profile_captures": (
                "Older usable snapshots of a currently exported section remain audit history and "
                "do not consume the bounded current candidate-evidence budget."
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
