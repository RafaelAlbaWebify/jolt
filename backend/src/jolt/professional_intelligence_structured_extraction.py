from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from jolt.professional_intelligence_evidence_review import (
    ProfessionalEvidenceRunReview,
    review_professional_capture_evidence,
)

_MAX_ITEMS_PER_SECTION = 20
_MAX_SNIPPET_LENGTH = 280

_ROLE_TERMS = [
    "Application Support",
    "Technical Support",
    "Software Support",
    "Production Support",
    "SaaS Support",
    "Service Manager",
    "Azure Cloud Engineer",
    "IT Support Engineer",
    "Local IT Engineer",
    "Systems Administrator",
    "Cloud Engineer",
]
_LOCATION_TERMS = ["Vigo", "Galicia", "Spain", "Ireland", "Dublin", "United Kingdom", "UK"]
_SKILL_TERMS = [
    "Active Directory",
    "Entra ID",
    "Microsoft 365",
    "ServiceNow",
    "PowerShell",
    "Windows",
    "Linux",
    "Azure",
    "AWS",
    "VMware",
    "DNS",
    "DHCP",
    "GPO",
    "SQL",
    "Python",
    "FastAPI",
    "React",
    "Playwright",
    "incident management",
    "change management",
    "problem management",
]
_CERTIFICATION_TERMS = [
    "AWS Cloud Solutions Architect",
    "AWS Cloud Technology Consultant",
    "Google Cybersecurity",
    "Google Data Analytics",
    "Google Project Management",
    "IBM Applied DevOps Engineering",
    "Microsoft Security Essentials",
]
_EMPLOYER_TERMS = [
    "FORVIA",
    "Faurecia",
    "Quental",
    "Auxilion",
    "Communisis",
    "Webify Digital Solutions",
]
_JOB_INTEREST_TERMS = [
    "remote",
    "hybrid",
    "Application Support",
    "Technical Support Engineer",
    "Production Support",
    "SaaS Support",
    "Service Manager",
    "Azure Cloud Engineer",
]


class ProfessionalExtractedSignal(BaseModel):
    value: str
    source_id: str
    supporting_snippet: str
    confidence: str = "explicit_match"
    extraction_method: str = "deterministic_term_match"


class ProfessionalStructuredExtraction(BaseModel):
    capture_run_id: str
    extraction_method: str = "deterministic_bounded_v1"
    integrity_verified: bool = True
    role_signals: list[ProfessionalExtractedSignal]
    location_signals: list[ProfessionalExtractedSignal]
    skills: list[ProfessionalExtractedSignal]
    certifications: list[ProfessionalExtractedSignal]
    employers: list[ProfessionalExtractedSignal]
    job_interest_keywords: list[ProfessionalExtractedSignal]


def _normalized_snippets(text: str) -> list[str]:
    snippets: list[str] = []
    for raw in re.split(r"[\r\n]+|(?<=[.!?])\s+", text):
        snippet = " ".join(raw.split()).strip()
        if not snippet:
            continue
        snippets.append(snippet[:_MAX_SNIPPET_LENGTH])
    return snippets


def _rendered_text_sources(review: ProfessionalEvidenceRunReview) -> Iterable[tuple[str, str]]:
    for source in review.sources:
        for artifact in source.artifacts:
            if (
                artifact.artifact_type != "rendered_text_json"
                or not artifact.integrity_valid
                or not isinstance(artifact.content, dict)
            ):
                continue
            text = artifact.content.get("text")
            if isinstance(text, str) and text.strip():
                yield source.source_id, text


def _extract_terms(
    sources: Iterable[tuple[str, str]], terms: list[str]
) -> list[ProfessionalExtractedSignal]:
    results: list[ProfessionalExtractedSignal] = []
    seen: set[str] = set()
    for source_id, text in sources:
        for snippet in _normalized_snippets(text):
            lowered = snippet.casefold()
            for term in terms:
                key = term.casefold()
                if key in seen or key not in lowered:
                    continue
                results.append(
                    ProfessionalExtractedSignal(
                        value=term,
                        source_id=source_id,
                        supporting_snippet=snippet,
                    )
                )
                seen.add(key)
                if len(results) >= _MAX_ITEMS_PER_SECTION:
                    return results
    return results


def extract_professional_intelligence(
    session: Session, run_id: str
) -> ProfessionalStructuredExtraction:
    review = review_professional_capture_evidence(session, run_id)
    if not review.ready_for_analysis:
        raise ValueError(
            "Structured extraction requires a completed run with integrity-verified reviewed evidence."
        )

    sources = list(_rendered_text_sources(review))
    if not sources:
        raise ValueError("No integrity-verified rendered text is available for extraction.")

    return ProfessionalStructuredExtraction(
        capture_run_id=run_id,
        role_signals=_extract_terms(sources, _ROLE_TERMS),
        location_signals=_extract_terms(sources, _LOCATION_TERMS),
        skills=_extract_terms(sources, _SKILL_TERMS),
        certifications=_extract_terms(sources, _CERTIFICATION_TERMS),
        employers=_extract_terms(sources, _EMPLOYER_TERMS),
        job_interest_keywords=_extract_terms(sources, _JOB_INTEREST_TERMS),
    )
