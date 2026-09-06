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
_PROFILE_COMPLETENESS_COMPLETE_MARKER = "jolt profile section completeness: complete"
_PROFILE_COMPLETENESS_PARTIAL_MARKER = "jolt profile section completeness: partial"
_PROFILE_SCROLL_STRATEGY_MARKER = "jolt profile section scroll strategy:"
_PROFILE_NOTE_PREFIXES = {
    "completeness": "JOLT profile section completeness:",
    "stop_reason": "JOLT profile section stop reason:",
    "scroll_count": "JOLT profile section scroll count:",
    "character_count": "JOLT profile section character count:",
    "scroll_strategy": "JOLT profile section scroll strategy:",
    "furthest_scroll_position": "JOLT profile section furthest scroll position:",
    "viewport_extent": "JOLT profile section viewport extent:",
    "final_scroll_extent": "JOLT profile section final scroll extent:",
    "observed_movement": "JOLT profile section observed movement:",
    "scroll_required": "JOLT profile section scroll required:",
}
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
    return CandidateEvidenceSummary.model_validate(value).model_dump(mode="json")


def _canonical_profile_section_key(capture: LinkedInPresenceCapture) -> tuple[str, str]:
    candidate = capture.source_url.strip()
    if candidate:
        parts = urlsplit(candidate)
        path = parts.path.rstrip("/") + "/"
        canonical_url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))
    else:
        canonical_url = ""
    return capture.category.strip().casefold(), canonical_url.casefold()


def _is_linkedin_profile_detail_capture(capture: LinkedInPresenceCapture) -> bool:
    source_url = capture.source_url.strip().casefold()
    return "linkedin.com/in/" in source_url and "/details/" in source_url


def _parse_bool(value: str) -> bool | None:
    folded = value.strip().casefold()
    if folded == "true":
        return True
    if folded == "false":
        return False
    return None


def _profile_section_capture_metadata(capture: LinkedInPresenceCapture) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "completeness": "unknown",
        "stop_reason": "unknown",
        "scroll_count": None,
        "character_count": None,
        "scroll_strategy": "unknown",
        "furthest_scroll_position": None,
        "viewport_extent": None,
        "final_scroll_extent": None,
        "observed_movement": None,
        "scroll_required": None,
        "progressive_traversal_verified": False,
    }
    lines = [line.strip() for line in capture.notes.splitlines() if line.strip()]
    for key, prefix in _PROFILE_NOTE_PREFIXES.items():
        prefix_folded = prefix.casefold()
        value = next(
            (
                line[len(prefix) :].strip()
                for line in lines
                if line.casefold().startswith(prefix_folded)
            ),
            None,
        )
        if value is None:
            continue
        if key in {
            "scroll_count",
            "character_count",
            "furthest_scroll_position",
            "viewport_extent",
            "final_scroll_extent",
        }:
            try:
                metadata[key] = int(value)
            except ValueError:
                metadata[key] = None
        elif key in {"observed_movement", "scroll_required"}:
            metadata[key] = _parse_bool(value)
        else:
            metadata[key] = value

    strategy = str(metadata["scroll_strategy"])
    furthest = metadata["furthest_scroll_position"]
    viewport = metadata["viewport_extent"]
    extent = metadata["final_scroll_extent"]
    movement = metadata["observed_movement"]
    required = metadata["scroll_required"]
    stop_reason = metadata["stop_reason"]
    completeness = metadata["completeness"]

    recognized_strategy = strategy in {"window", "scrollable_container"}
    moved_when_required = (
        required is True
        and movement is True
        and isinstance(furthest, int)
        and furthest > 0
        and isinstance(extent, int)
        and isinstance(viewport, int)
        and extent > viewport + 2
    )
    defensible_no_scroll = (
        required is False
        and movement is False
        and isinstance(extent, int)
        and isinstance(viewport, int)
        and extent <= viewport + 2
    )
    metadata["progressive_traversal_verified"] = bool(
        completeness == "complete"
        and stop_reason == "stable_at_scroll_surface_end"
        and recognized_strategy
        and (moved_when_required or defensible_no_scroll)
    )
    return metadata


def profile_capture_quality_issue(capture: LinkedInPresenceCapture) -> str | None:
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
    if _is_linkedin_profile_detail_capture(capture):
        if _PROFILE_COMPLETENESS_COMPLETE_MARKER not in notes:
            return "unverified_linkedin_profile_section_completeness"
        if _PROFILE_SCROLL_STRATEGY_MARKER not in notes:
            return "legacy_non_scroll_surface_profile_section"
        metadata = _profile_section_capture_metadata(capture)
        if not metadata["progressive_traversal_verified"]:
            return "unverified_linkedin_profile_section_traversal"
    return None


def validate_candidate_evidence_refs(session: Session, value: dict[str, Any]) -> None:
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
            "capture_metadata": _profile_section_capture_metadata(capture),
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
                "Newest usable capture per canonical LinkedIn profile section, with provenance and "
                "recorder-owned completeness/traversal metadata. Presence of a term does not prove "
                "professional depth or duration."
            ),
            "excluded_profile_captures": (
                "LinkedIn login/authwall/checkpoint, empty, explicitly partial, or traversal-"
                "unverifiable profile-detail captures are retained for audit but are not candidate evidence."
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
