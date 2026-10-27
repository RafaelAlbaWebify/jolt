"""Conservative evidence preflight: no network access and no invented verification.

This layer collects candidate employer ATS URLs and application-method observations.
Actual HTTP/browser retrieval is a separate, auditable capture step.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_ATS_DOMAINS = (
    "greenhouse.io", "lever.co", "ashbyhq.com", "workdayjobs.com",
    "myworkdayjobs.com", "smartrecruiters.com", "teamtailor.com",
    "recruitee.com", "personio.com", "bamboohr.com", "jobvite.com",
    "icims.com", "applytojob.com",
)
_AGGREGATORS = ("linkedin.com", "indeed.com", "glassdoor.", "jobgether.com")
_EASY = re.compile(r"(?<![a-z])(?:easy\\s+apply|solicitud\\s+sencilla|solicitud\\s+fácil)(?![a-z])", re.I)


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def _extract_ats_candidates(text: str, source_url: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _URL.finditer(text):
        url = match.group(0).rstrip(".,;")
        host = _host(url)
        if not host or any(host == site or host.endswith("." + site) for site in _AGGREGATORS):
            continue
        if not any(host == site or host.endswith("." + site) for site in _ATS_DOMAINS):
            continue
        if url in seen or url == source_url:
            continue
        seen.add(url)
        candidates.append({"url": url, "source": "captured_text", "verification_status": "unverified_candidate"})
    return candidates[:8]


def build_job_preflight(job: dict[str, Any]) -> dict[str, Any]:
    """Read job capture without extrapolating from absent or ambiguous UI elements."""
    text = str(job.get("analysis_text", ""))
    source_url = str(job.get("source_url", ""))
    # Text may describe a site's general Easy Apply feature, so evidence is advisory only.
    easy_mentioned = bool(_EASY.search(text))
    candidates = _extract_ats_candidates(text, source_url)
    outbound = str(job.get("outbound_application_url", ""))
    if outbound.startswith("https://") and any(
        _host(outbound) == domain or _host(outbound).endswith("." + domain)
        for domain in _ATS_DOMAINS
    ):
        if outbound not in {item["url"] for item in candidates}:
            candidates.insert(0, {
                "url": outbound,
                "source": "captured_apply_control",
                "verification_status": "unverified_candidate",
            })
    return {
        "version": "1.0",
        "official_source_candidates": candidates,
        "external_source_status": "not_checked",
        "external_source_checks": [],
        "external_capture_policy": {
            "verify_posting_identity": True,
            "respect_robots_terms_rate_limits": True,
            "no_auth_or_access_bypass": True,
            "record_source_url_timestamp_hash_and_result": True,
            "prefer_employer_controlled_sources": True,
        },
        "application_method": str(job.get("application_method") or "unknown"),
        "easy_apply_available": job.get("easy_apply_available"),
        "easy_apply_text_mention": easy_mentioned,
        "easy_apply_verification_status": (
            "observed_job_button" if type(job.get("easy_apply_available")) is bool
            else "unverified"
        ),
        "application_url": outbound or source_url,
        "last_checked_at": job.get("easy_apply_observed_at"),
        "needs_ui_observation": type(job.get("easy_apply_available")) is not bool,
        "reason": "A textual mention is not proof that the job's Easy Apply button is available.",
    }


def attach_preflight(inbox: dict[str, Any] | None) -> dict[str, Any] | None:
    if inbox is None:
        return None
    jobs = inbox.get("jobs")
    if not isinstance(jobs, list):
        return inbox
    candidates = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        evidence = build_job_preflight(job)
        job["external_evidence_preflight"] = evidence
        candidates += int(bool(evidence["official_source_candidates"]))
    inbox["preflight_metadata"] = {
        "version": "1.0",
        "jobs_processed": sum(isinstance(job, dict) for job in jobs),
        "jobs_with_official_candidate_links": candidates,
        "externally_verified_jobs": 0,
        "note": "This phase extracts candidates only; it does not fetch or verify websites.",
    }
    return inbox


def sort_application_priority(decision_rank: int, fit_score: int | None, easy_apply: bool | None,
                              title: str) -> tuple[int, int, int, str]:
    """Easy Apply leads within a classification; score breaks ties within each method."""
    return decision_rank, 0 if easy_apply is True else 1, -(fit_score or 0), title.casefold()
