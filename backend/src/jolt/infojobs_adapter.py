"""InfoJobs official REST API adapter foundation (offline and credential-free).

This module deliberately performs no network calls or database mutations.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

SEARCH_ENDPOINT = "https://api.infojobs.net/api/9/offer"
DETAIL_ENDPOINT = "https://api.infojobs.net/api/7/offer"


@dataclass(frozen=True)
class InfoJobsCandidate:
    source: str
    source_job_id: str
    source_url: str
    title: str
    company: str
    location: str


def search_url(
    keywords: str, *, page: int = 1, max_results: int = 20, province: str = ""
) -> str:
    """Construct a bounded API search URL using documented query parameters."""
    if not keywords.strip():
        raise ValueError("keywords are required")
    if page < 1 or not 1 <= max_results <= 50:
        raise ValueError("page must be >=1 and max_results between 1 and 50")
    params: dict[str, str | int] = {
        "q": keywords.strip(),
        "page": page,
        "maxResults": max_results,
    }
    if province:
        params["province"] = province
    return f"{SEARCH_ENDPOINT}?{urlencode(params)}"


def detail_url(source_job_id: str) -> str:
    """Only offer identifiers, never arbitrary paths or URLs."""
    if not source_job_id or not all(
        char.isascii() and (char.isalnum() or char in "-_")
        for char in source_job_id
    ):
        raise ValueError("invalid InfoJobs offer identifier")
    return f"{DETAIL_ENDPOINT}/{source_job_id}"


def _name(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or value.get("name") or "").strip()
    return str(value or "").strip()


def parse_listing(value: object) -> InfoJobsCandidate:
    """Fail closed when official API listing identity or essential fields are absent."""
    if not isinstance(value, dict):
        raise ValueError("listing must be an object")
    job_id = str(value.get("id") or "").strip()
    detail_url(job_id)
    title = str(value.get("title") or "").strip()
    link = str(value.get("link") or "").strip()
    author = value.get("author")
    company = _name(author.get("name")) if isinstance(author, dict) else ""
    city = str(value.get("city") or "").strip()
    province = _name(value.get("province"))
    location = ", ".join(piece for piece in (city, province) if piece)
    if not title or not company or not location:
        raise ValueError("listing lacks reliable title/company/location")
    if not link.startswith(("https://www.infojobs.net/", "https://infojobs.net/")):
        raise ValueError("listing lacks a canonical InfoJobs URL")
    return InfoJobsCandidate(
        source="infojobs",
        source_job_id=job_id,
        source_url=link,
        title=title,
        company=company,
        location=location,
    )


def parse_search_page(value: object) -> tuple[list[InfoJobsCandidate], int, int]:
    """Parse official page metadata and accepted identities; never silently skip errors."""
    if not isinstance(value, dict) or not isinstance(value.get("offers"), list):
        raise ValueError("invalid InfoJobs offer listing response")
    current_page = int(value.get("currentPage", 0))
    total_pages = int(value.get("totalPages", 0))
    if current_page < 1 or total_pages < current_page:
        raise ValueError("invalid pagination metadata")
    offers = [parse_listing(offer) for offer in value["offers"]]
    ids = [offer.source_job_id for offer in offers]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source IDs within a page")
    return offers, current_page, total_pages
