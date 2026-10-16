"""Conservative cross-portal duplicate decisions for normalized job offers.

This module does not mutate Postings or collapse source evidence. Durable
multi-source linking follows in Phase 1.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from jolt.semantic_duplicates import (
    descriptions_are_materially_similar,
    normalize_duplicate_text,
)
from jolt.sources.normalized_offer import NormalizedJobOffer

Decision = Literal["same_source_offer", "probable_same_vacancy", "distinct", "needs_review"]


@dataclass(frozen=True)
class DuplicateAssessment:
    decision: Decision
    reason: str


def assess_duplicate(
    first: NormalizedJobOffer,
    second: NormalizedJobOffer,
) -> DuplicateAssessment:
    """Never auto-merge cross-site vacancies on title or description alone."""
    if first.portal == second.portal and first.source_job_id == second.source_job_id:
        return DuplicateAssessment("same_source_offer", "Same portal and durable source ID")

    # A mirrored job at another board needs independent corroboration:
    # same named employer, title, geographic context and substantial description.
    first_company = normalize_duplicate_text(first.company)
    second_company = normalize_duplicate_text(second.company)
    first_title = normalize_duplicate_text(first.title)
    second_title = normalize_duplicate_text(second.title)

    if not first_title or not first_company or first_title != second_title:
        return DuplicateAssessment("distinct", "Titles differ or required identity is absent")
    if first_company != second_company:
        return DuplicateAssessment("needs_review", "Same title but different advertised employer")

    first_location = normalize_duplicate_text(first.location)
    second_location = normalize_duplicate_text(second.location)
    if first_location and second_location and first_location != second_location:
        return DuplicateAssessment(
            "needs_review", "Different locations could reflect separate vacancies"
        )
    if not first_location or not second_location:
        return DuplicateAssessment("needs_review", "Location comparison is incomplete")
    if not first.description.strip() or not second.description.strip():
        return DuplicateAssessment("needs_review", "Full descriptions are unavailable")
    if not first.detail_verified or not second.detail_verified:
        return DuplicateAssessment("needs_review", "Detail evidence is not yet verified")
    if descriptions_are_materially_similar(first.description, second.description):
        return DuplicateAssessment(
            "probable_same_vacancy",
            "Employer, title, location and validated job descriptions agree",
        )
    return DuplicateAssessment("distinct", "Job descriptions differ materially")
