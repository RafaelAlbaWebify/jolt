from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from jolt import multipage_capture

_LINKEDIN_ROOT = "https://www.linkedin.com/"
_ORIGINAL_CARD_IDENTITY = multipage_capture._card_identity
_INSTALLED = False


def absolute_linkedin_url(source_url: str) -> str:
    value = source_url.strip()
    if not value:
        return ""
    return urljoin(_LINKEDIN_ROOT, value)


def _normalized_card_identity(card: Any, title_link: Any = None) -> tuple[str, str]:
    source_job_id, source_url = _ORIGINAL_CARD_IDENTITY(card, title_link)
    return source_job_id, absolute_linkedin_url(source_url)


def install_linkedin_url_normalization() -> None:
    """Normalize captured job-card href values at the shared identity boundary."""
    global _INSTALLED
    if _INSTALLED:
        return
    setattr(multipage_capture, "_card_identity", _normalized_card_identity)
    _INSTALLED = True
