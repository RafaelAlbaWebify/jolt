from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from jolt.capture_ingestion import ingest_capture_item
from jolt.professional_intelligence_capture_runs import get_professional_capture_run
from jolt.professional_intelligence_evidence_review import (
    ProfessionalEvidenceRunReview,
    review_professional_capture_evidence,
)
from jolt.professional_intelligence_sources import ProfessionalIntelligenceSource
from jolt.schemas import ManualIntakeRequest

_ROLE_PATTERNS = (
    "application support",
    "technical support",
    "software support",
    "production support",
    "saas support",
    "it support",
    "support engineer",
    "systems administrator",
    "system administrator",
    "cloud engineer",
    "azure cloud engineer",
    "service manager",
)
_LOCATION_HINTS = (
    "remote",
    "hybrid",
    "spain",
    "galicia",
    "vigo",
    "madrid",
    "barcelona",
    "ireland",
    "dublin",
    "portugal",
    "uk",
    "united kingdom",
)
_MAX_CANDIDATES_PER_SOURCE = 8
_MAX_DESCRIPTION_LINES = 10


class ProfessionalOpportunityCandidateImport(BaseModel):
    title: str
    company: str
    location: str
    source_id: str
    source_url: str
    posting_id: str
    source_document_id: str
    evaluation_id: str
    identity_status: str
    recommendation: str
    ranking_score: int


class ProfessionalOpportunityImportResult(BaseModel):
    capture_run_id: str
    imported_count: int
    skipped_count: int
    candidates: list[ProfessionalOpportunityCandidateImport]
    warnings: list[str] = []


def _rendered_text_sources(
    review: ProfessionalEvidenceRunReview,
) -> Iterable[tuple[str, str, str]]:
    for source in review.sources:
        for artifact in source.artifacts:
            if (
                artifact.artifact_type != "rendered_text_json"
                or not artifact.integrity_valid
                or not isinstance(artifact.content, dict)
            ):
                continue
            text = artifact.content.get("text")
            source_url = artifact.content.get("source_url")
            if isinstance(text, str) and text.strip():
                yield source.source_id, str(source_url or ""), text


def _line_has_role(line: str) -> bool:
    lowered = line.casefold()
    return any(pattern in lowered for pattern in _ROLE_PATTERNS)


def _looks_like_noise(line: str) -> bool:
    lowered = line.casefold()
    if len(line) < 6 or len(line) > 130:
        return True
    if lowered.startswith(("recommended", "jobs based", "show all", "see more", "sort by")):
        return True
    return "linkedin" in lowered and not _line_has_role(line)


def _looks_like_location(line: str) -> bool:
    lowered = line.casefold()
    return any(hint in lowered for hint in _LOCATION_HINTS)


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in re.split(r"[\r\n]+", text):
        line = " ".join(raw.split()).strip()
        if line:
            lines.append(line)
    return lines


def _career_sources(run_sources: list[ProfessionalIntelligenceSource]) -> set[str]:
    return {
        source.source_id
        for source in run_sources
        if source.category == "career" or "job" in source.source_id.casefold()
    }


def _extract_candidates_from_text(
    *,
    source_id: str,
    source_url: str,
    text: str,
) -> list[ManualIntakeRequest]:
    lines = _clean_lines(text)
    candidates: list[ManualIntakeRequest] = []
    seen_titles: set[str] = set()
    for index, line in enumerate(lines):
        if _looks_like_noise(line) or not _line_has_role(line):
            continue
        normalized_title = line.casefold()
        if normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)

        company = "LinkedIn captured source"
        location = ""
        following = lines[index + 1 : index + 1 + _MAX_DESCRIPTION_LINES]
        if following:
            first = following[0]
            if not _looks_like_location(first) and not _line_has_role(first) and len(first) <= 90:
                company = first
                following = following[1:]
        for candidate_line in following[:3]:
            if _looks_like_location(candidate_line):
                location = candidate_line
                break

        description_lines = [line, *following]
        raw_text = "\n".join(
            part
            for part in [
                line,
                company,
                f"Location: {location}" if location else "",
                "\n".join(description_lines),
            ]
            if part
        )
        candidates.append(
            ManualIntakeRequest(
                raw_text=raw_text,
                source_url=source_url,
                source_type="professional_career_capture",
            )
        )
        if len(candidates) >= _MAX_CANDIDATES_PER_SOURCE:
            break
    return candidates


def import_professional_opportunity_candidates(
    session: Session,
    capture_run_id: str,
) -> ProfessionalOpportunityImportResult:
    run = get_professional_capture_run(session, capture_run_id)
    career_source_ids = _career_sources(run.planned_sources)
    if not career_source_ids:
        return ProfessionalOpportunityImportResult(
            capture_run_id=capture_run_id,
            imported_count=0,
            skipped_count=0,
            candidates=[],
            warnings=["Capture run has no career/job sources that can feed Review Inbox."],
        )

    review = review_professional_capture_evidence(session, capture_run_id)
    if not review.ready_for_analysis:
        raise ValueError(
            "Opportunity import requires a completed run with integrity-verified rendered text."
        )

    imported: list[ProfessionalOpportunityCandidateImport] = []
    skipped = 0
    warnings: list[str] = []
    for source_id, source_url, text in _rendered_text_sources(review):
        if source_id not in career_source_ids:
            continue
        candidates = _extract_candidates_from_text(
            source_id=source_id,
            source_url=source_url,
            text=text,
        )
        if not candidates:
            warnings.append(f"No job-like rows were extracted from career source {source_id}.")
            continue
        for candidate in candidates:
            intake = ingest_capture_item(
                session,
                candidate,
                use_source_url_for_identity=False,
            )
            if intake.identity_status == "confirmed_duplicate":
                skipped += 1
                continue
            imported.append(
                ProfessionalOpportunityCandidateImport(
                    title=intake.title,
                    company=intake.company,
                    location=intake.location,
                    source_id=source_id,
                    source_url=source_url,
                    posting_id=intake.posting_id,
                    source_document_id=intake.source_document_id,
                    evaluation_id=intake.evaluation_id,
                    identity_status=intake.identity_status,
                    recommendation=intake.recommendation,
                    ranking_score=intake.ranking_score,
                )
            )
    session.commit()
    return ProfessionalOpportunityImportResult(
        capture_run_id=capture_run_id,
        imported_count=len(imported),
        skipped_count=skipped,
        candidates=imported,
        warnings=warnings,
    )
