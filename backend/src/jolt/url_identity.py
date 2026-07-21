from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_LINKEDIN_JOB_PATH = re.compile(r"^/jobs/view/(?:[^/?#]*-)?(?P<job_id>\d+)(?:/)?$")


def linkedin_job_id(value: str) -> str:
    """Extract LinkedIn's stable numeric job ID from a job-detail URL."""
    if not value.strip():
        return ""
    parts = urlsplit(value.strip())
    if parts.hostname not in {"linkedin.com", "www.linkedin.com"}:
        return ""
    match = _LINKEDIN_JOB_PATH.match(parts.path.rstrip("/"))
    return match.group("job_id") if match else ""


def canonicalize_source_url(value: str) -> str:
    """Return a stable posting identity while preserving non-identity source evidence elsewhere."""
    if not value.strip():
        return ""
    job_id = linkedin_job_id(value)
    if job_id:
        return f"https://www.linkedin.com/jobs/view/{job_id}"

    parts = urlsplit(value.strip())
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"trk", "ref", "refid"}
    ]
    return urlunsplit(parts._replace(query=urlencode(query), fragment="")).rstrip("/")
