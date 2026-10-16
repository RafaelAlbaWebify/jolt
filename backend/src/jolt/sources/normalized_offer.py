"""Common, source-independent job offer contract.

Capturers retain their portal-specific evidence. This model normalizes the
shared fields without treating captured metadata as independently verified.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Portal = Literal["linkedin", "indeed", "infojobs", "jobgether"]
WorkMode = Literal["remote", "hybrid", "on_site", "unknown"]


class NormalizedJobOffer(BaseModel):
    """Shared hand-off shape; not a promise of employability or job validity."""

    portal: Portal
    source_job_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    location: str = ""
    description: str = ""
    work_mode: WorkMode = "unknown"
    salary_text: str | None = None
    contract_type: str | None = None
    experience_text: str | None = None
    languages: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    observed_at: datetime | None = None
    identity_verified: bool = False
    detail_verified: bool = False
    work_from_spain_verified: bool = False
    source_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_job_id", "title", "company")
    @classmethod
    def strip_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required offer field cannot be blank")
        return value.strip()

    @field_validator("source_url")
    @classmethod
    def require_trusted_url(cls, value: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        domains = {
            "linkedin": {"linkedin.com", "www.linkedin.com"},
            "indeed": {"indeed.com", "www.indeed.com", "es.indeed.com"},
            "infojobs": {"infojobs.net", "www.infojobs.net"},
            "jobgether": {"jobgether.com", "www.jobgether.com"},
        }
        # The portal name is checked in the adapter, not inferred from URLs.
        if parsed.scheme != "https" or parsed.hostname not in set().union(*domains.values()):
            raise ValueError("source_url must be a trusted HTTPS job portal URL")
        return value


def normalize_captured_offer(
    portal: Portal,
    evidence: dict[str, Any],
) -> NormalizedJobOffer:
    """Map existing portal payloads into one contract without modifying capturers.

    This does not persist Postings or perform cross-source deduplication.
    InfoJobs isolated descriptions receive their structural/hash validation.
    Other sources only claim identity_verified when the capture explicitly does.
    """

    raw = dict(evidence)
    if portal == "infojobs":
        from jolt.infojobs_observations import inspect_offer

        parsed = inspect_offer(raw)
        return NormalizedJobOffer(
            portal=portal,
            source_job_id=parsed["source_job_id"],
            source_url=parsed["url"],
            title=parsed["title"],
            company=parsed["company"],
            location=parsed["location"],
            description=parsed["description"],
            identity_verified=True,
            detail_verified=True,
            source_metadata=raw,
        )

    if portal == "jobgether":
        from jolt.jobgether_preview import jobgether_identity

        url = str(raw.get("url") or raw.get("source_url") or "")
        identifier = jobgether_identity(url)
        if not identifier or (raw.get("source_job_id") and raw["source_job_id"] != identifier):
            raise ValueError("Jobgether source identity mismatch")
        if raw.get("mismatches"):
            raise ValueError("Jobgether structured evidence has mismatches")
        title = str(raw.get("title") or "")
        company = str(raw.get("company") or "")
        desc = str(raw.get("description") or "")
        complete = raw.get("status") == "extracted_unverified" and len(desc.strip()) >= 150
        return NormalizedJobOffer(
            portal=portal,
            source_job_id=identifier,
            source_url=url,
            title=title,
            company=company,
            location=str(raw.get("location") or ""),
            description=desc,
            contract_type=str(raw["contract_type"]) if raw.get("contract_type") else None,
            identity_verified=complete,
            detail_verified=complete,
            source_metadata=raw,
        )

    if portal not in {"linkedin", "indeed"}:
        raise ValueError("Unsupported source")
    url = str(raw.get("source_url") or "")
    from urllib.parse import urlparse

    host = urlparse(url).hostname
    allowed_hosts = {
        "linkedin": {"linkedin.com", "www.linkedin.com"},
        "indeed": {"indeed.com", "www.indeed.com", "es.indeed.com"},
    }
    if host not in allowed_hosts[portal]:
        raise ValueError(f"{portal} offer URL does not belong to its portal")

    checked = bool(raw.get("identity_verified", False))
    return NormalizedJobOffer(
        portal=portal,
        source_job_id=str(raw.get("source_job_id") or ""),
        source_url=url,
        title=str(raw.get("title") or ""),
        company=str(raw.get("company") or ""),
        location=str(raw.get("location") or ""),
        description=str(raw.get("description") or ""),
        identity_verified=checked,
        detail_verified=checked and bool(str(raw.get("description") or "").strip()),
        source_metadata=raw,
    )
