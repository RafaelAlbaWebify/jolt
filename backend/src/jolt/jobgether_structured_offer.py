"""Read-only extraction of Jobgether JobPosting JSON-LD from supervised pages.

The canonical URL is JOLT's source identity. JSON-LD identifiers are retained
separately. Extraction does not establish vacancy status or employment eligibility.
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from typing import Any

from jolt.jobgether_preview import jobgether_identity


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "br", "li", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")


def _text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    parser = _PlainText()
    parser.feed(value)
    return re.sub(r"[ \t]+", " ", html.unescape("".join(parser.parts))).strip()


def _nodes(payload: object) -> list[dict[str, Any]]:
    pending = [payload]
    found: list[dict[str, Any]] = []
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, dict):
            graph = item.get("@graph")
            if isinstance(graph, (list, dict)):
                pending.append(graph)
            types = item.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if isinstance(types, list) and "JobPosting" in types:
                found.append(item)
    return found


def _countries(value: object) -> list[str]:
    items = value if isinstance(value, list) else [value]
    names: set[str] = set()
    for item in items:
        if isinstance(item, str):
            names.add(item.strip())
        elif isinstance(item, dict):
            for key in ("name", "addressCountry"):
                country = item.get(key)
                if isinstance(country, str):
                    names.add(country.strip())
                elif isinstance(country, dict) and isinstance(country.get("name"), str):
                    names.add(country["name"].strip())
    return sorted(name for name in names if name)


def extract_offer(url: str, scripts: list[str], visible_title: str = "") -> dict[str, object]:
    """Extract deterministic evidence without inferring verification or eligibility."""
    source_id = jobgether_identity(url)
    if source_id is None:
        return {"status": "unresolved", "reason": "invalid_source_url"}

    postings: list[dict[str, Any]] = []
    parse_errors = 0
    for script in scripts:
        try:
            postings.extend(_nodes(json.loads(script)))
        except (ValueError, TypeError):
            parse_errors += 1

    if len(postings) != 1:
        return {
            "status": "unresolved",
            "reason": "jobposting_count_not_one",
            "source_job_id": source_id,
            "jobposting_count": len(postings),
            "parse_errors": parse_errors,
        }

    posting = postings[0]
    title = _text(posting.get("title"))
    description = _text(posting.get("description"))
    hiring = posting.get("hiringOrganization")
    company = hiring.get("name", "") if isinstance(hiring, dict) else ""
    identifier = posting.get("identifier")
    structured_id = identifier.get("value") if isinstance(identifier, dict) else identifier
    structured_id = structured_id if isinstance(structured_id, str) else ""
    structured_url = posting.get("url")
    structured_url = structured_url if isinstance(structured_url, str) else ""
    structured_url_id = jobgether_identity(structured_url) if structured_url else None

    mismatches: list[str] = []
    if (
        visible_title
        and title
        and re.sub(r"\s+", " ", visible_title).strip().casefold() != title.casefold()
    ):
        mismatches.append("visible_title")
    if structured_url and structured_url_id != source_id:
        mismatches.append("structured_url")

    countries = _countries(posting.get("applicantLocationRequirements"))
    return {
        "status": "extracted_unverified"
        if title and description and not mismatches
        else "unresolved",
        "source_job_id": source_id,
        "url": url,
        "structured_identifier": structured_id,
        "structured_url": structured_url,
        "title": title,
        "company": _text(company),
        "description": description,
        "description_length": len(description),
        "date_posted": posting.get("datePosted"),
        "valid_through": posting.get("validThrough"),
        "employment_type": posting.get("employmentType"),
        "job_location_type": posting.get("jobLocationType"),
        "applicant_countries": countries,
        "spain_declared": any(c.casefold() in {"es", "esp", "spain", "españa"} for c in countries),
        "mismatches": mismatches,
        "parse_errors": parse_errors,
        "source_evidence_verified": False,
        "work_from_spain_verified": False,
    }
