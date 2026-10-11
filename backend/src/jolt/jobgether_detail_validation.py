"""Check structural consistency of supplied Jobgether detail evidence."""

from __future__ import annotations

from urllib.parse import urlparse

from jolt.jobgether_preview import jobgether_identity


def validate_jobgether_detail(
    *, observed_id: str, observed_url: str, detail_url: str, title: str,
    company: str, description: str,
) -> dict:
    """Structural checks only: caller-provided text is NOT verified source evidence."""
    reasons: list[str] = []
    reference_id = jobgether_identity(observed_url)
    detail_id = jobgether_identity(detail_url)
    if not reference_id or reference_id != observed_id:
        reasons.append("observed_identity_invalid")
    if not detail_id or detail_id != observed_id:
        reasons.append("detail_identity_mismatch")
    if urlparse(detail_url).hostname not in {"jobgether.com", "www.jobgether.com"}:
        reasons.append("detail_source_untrusted")
    if not title.strip():
        reasons.append("missing_title")
    if not company.strip():
        reasons.append("missing_company")
    if len(description.strip()) < 100:
        reasons.append("insufficient_description")
    return {
        "source_job_id": observed_id,
        "identity_consistent": not reasons,
        "description_structurally_sufficient": not reasons,
        "source_evidence_verified": False,
        "work_from_spain_verified": False,
        "reasons": reasons,
    }
