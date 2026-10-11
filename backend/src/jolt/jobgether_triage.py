"""Conservative triage of unverified Jobgether API observations.

No decisions, eligibility assertions, or posting writes are made here.
"""

from __future__ import annotations


def triage_jobgether_observation(job: dict) -> dict:
    """Return advisory ranking signals, preserving every original observation."""
    flags = set(job.get("quality_flags") or [])
    title = str(job.get("title") or "").casefold()
    contract = str(job.get("contract_type") or "").casefold()
    location = str(job.get("location") or "").casefold()
    remote = str(job.get("remote") or "").casefold()

    caution: list[str] = []
    if "older_than_30_days" in flags:
        caution.append("stale_listing")
    if "possible_inactive_title" in flags:
        caution.append("potentially_closed")
    if "internship_title" in flags or "internship" in contract:
        caution.append("internship")
    if not job.get("posted_at"):
        caution.append("unknown_publication_date")

    support_terms = ("support", "helpdesk", "help desk", "service desk", "technical")
    signals = [
        "support_title_match"
        for _ in [0]
        if any(term in title for term in support_terms)
    ]
    if "spain" in location or "españa" in location:
        signals.append("spain_listed")
    if "remote" in remote:
        signals.append("remote_label")

    return {
        "source_job_id": job.get("source_job_id"),
        "priority": "review_later" if caution else "review_first",
        "positive_signals": signals,
        "cautions": caution,
        "work_from_spain_verified": False,
        "full_description_verified": False,
    }


def triage_jobgether_preview(preview: dict) -> dict:
    """Sort an in-memory preview; do not discard or mutate its jobs."""
    rows = [triage_jobgether_observation(job) for job in preview.get("jobs", [])]
    return {
        "source": "jobgether",
        "count": len(rows),
        "ranked": sorted(
            rows,
            key=lambda item: (
                item["priority"] != "review_first",
                -len(item["positive_signals"]),
            ),
        ),
    }
