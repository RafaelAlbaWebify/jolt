from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from jolt import multipage_capture

_LINKEDIN_ROOT = "https://www.linkedin.com/"
_TRANSIENT_SEARCH_QUERY_KEYS = {
    "currentJobId",
    "trackingId",
    "refId",
    "origin",
    "refresh",
}
_ORIGINAL_CARD_IDENTITY = multipage_capture._card_identity
_INSTALLED = False


def absolute_linkedin_url(source_url: str) -> str:
    value = source_url.strip()
    if not value:
        return ""
    return urljoin(_LINKEDIN_ROOT, value)


def normalize_linkedin_search_url(source_url: str) -> str:
    """Remove transient LinkedIn UI state while preserving real search criteria."""
    value = source_url.strip()
    if not value:
        return ""

    parsed = urlsplit(value)

    if not parsed.netloc.casefold().endswith("linkedin.com"):
        return value

    if not parsed.path.startswith("/jobs/search"):
        return value

    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in _TRANSIENT_SEARCH_QUERY_KEYS
    ]

    return urlunsplit(
        (
            parsed.scheme or "https",
            parsed.netloc,
            parsed.path,
            urlencode(query, doseq=True),
            "",
        )
    )


def _normalized_card_identity(card: Any, title_link: Any = None) -> tuple[str, str]:
    source_job_id, source_url = _ORIGINAL_CARD_IDENTITY(card, title_link)
    return source_job_id, absolute_linkedin_url(source_url)


def install_linkedin_url_normalization() -> None:
    """Normalize captured job-card href values at the shared identity boundary."""
    global _INSTALLED
    if _INSTALLED:
        return
    multipage_capture._card_identity = _normalized_card_identity
    _INSTALLED = True
