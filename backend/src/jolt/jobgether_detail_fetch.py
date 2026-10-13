"""Bounded, read-only official Jobgether detail fetch with conservative JSON-LD extraction.

This module never writes Postings, reviews, applications, or capture evidence.
A page without accessible JobPosting structured data stays unresolved.
"""

from __future__ import annotations

import json
import urllib.request
from html.parser import HTMLParser

from jolt.jobgether_detail_validation import validate_jobgether_detail
from jolt.jobgether_preview import jobgether_identity


class _StructuredData(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.collecting = False
        self.blocks: list[str] = []
        self.current: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type") == "application/ld+json":
            self.collecting = True
            self.current = []

    def handle_data(self, data: str) -> None:
        if self.collecting:
            self.current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.collecting:
            self.blocks.append("".join(self.current))
            self.collecting = False


def _jobposting_documents(markup: str) -> list[dict]:
    parser = _StructuredData()
    parser.feed(markup)
    matches = []
    for raw in parser.blocks:
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            continue
        queue = parsed if isinstance(parsed, list) else [parsed]
        while queue:
            item = queue.pop()
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "JobPosting" or (
                isinstance(item.get("@type"), list) and "JobPosting" in item["@type"]
            ):
                matches.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
    return matches


def extract_jobgether_detail(markup: str, *, observed_id: str, observed_url: str) -> dict:
    """Validate source identity and structured description without inferring eligibility."""
    if jobgether_identity(observed_url) != observed_id:
        raise ValueError("Observed Jobgether offer ID does not match URL")
    matches = _jobposting_documents(markup)
    if len(matches) != 1:
        return {
            "source_job_id": observed_id,
            "status": "unresolved",
            "reason": "jobposting_schema_missing_or_ambiguous",
        }
    job = matches[0]
    title = str(job.get("title") or "")
    organization = job.get("hiringOrganization")
    company = str(organization.get("name") or "") if isinstance(organization, dict) else ""
    description = str(job.get("description") or "")
    result = validate_jobgether_detail(
        observed_id=observed_id,
        observed_url=observed_url,
        detail_url=observed_url,
        title=title,
        company=company,
        description=description,
    )
    return {
        "source_job_id": observed_id,
        "status": "structured_detail_present" if result["identity_consistent"] else "unresolved",
        "title": title,
        "company": company,
        "description": description,
        "validation": result,
        "source_evidence_verified": False,
        "work_from_spain_verified": False,
    }


def fetch_jobgether_detail(*, observed_id: str, observed_url: str) -> dict:
    """One HTTPS page request, bounded to 2 MB; no browser evasion or redirects off source."""
    if jobgether_identity(observed_url) != observed_id:
        raise ValueError("Only canonical matching Jobgether offer URLs can be fetched")
    request = urllib.request.Request(
        observed_url, headers={"Accept": "text/html", "User-Agent": "JOLT/0.8"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        final_url = response.geturl()
        if jobgether_identity(final_url) != observed_id:
            raise ValueError("Jobgether detail redirected to a different source identity")
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Jobgether detail exceeds size limit")
        if "html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("Jobgether detail response was not HTML")
    return extract_jobgether_detail(
        raw.decode("utf-8", errors="replace"),
        observed_id=observed_id,
        observed_url=observed_url,
    )
