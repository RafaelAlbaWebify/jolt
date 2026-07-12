from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ListingCandidate:
    source: str
    source_job_id: str
    source_url: str
    title: str
    company: str
    location: str
    summary: str = ""
    page_number: int = 1
    position: int = 0


@dataclass(frozen=True)
class DetailEvidence:
    source: str
    source_job_id: str
    source_url: str
    title: str
    company: str
    location: str
    description: str
    identity_verified: bool
    verification_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PaginationEvidence:
    page_number: int
    visible_job_ids: tuple[str, ...]
    next_control_present: bool
    next_control_enabled: bool


@dataclass(frozen=True)
class CaptureRunEvidence:
    listings: tuple[ListingCandidate, ...]
    details: tuple[DetailEvidence, ...] = ()
    pages: tuple[PaginationEvidence, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)


class SourceAdapter(Protocol):
    source_name: str

    def parse_listing_page(self, html: str, page_number: int = 1) -> CaptureRunEvidence: ...

    def parse_detail_page(self, html: str, expected: ListingCandidate) -> DetailEvidence: ...
