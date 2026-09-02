from __future__ import annotations

import re
from dataclasses import dataclass

from jolt.employment_geography import normalized_location_scope


@dataclass(frozen=True)
class LocationEvidenceResult:
    location_eligibility: str
    hardline_reject: bool
    positive_evidence: tuple[str, ...]
    negative_evidence: tuple[str, ...]


_NEGATIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("US-only", re.compile(r"\b(?:u\.?s\.?|united states)\s+only\b", re.I)),
    (
        "US remote",
        re.compile(
            r"\b(?:u\.?s\.?|usa|united states)\s*(?:[-·|/]\s*)?remote\b|\bremote\s*(?:[-·|/]\s*)?(?:usa|u\.?s\.?)\b",
            re.I,
        ),
    ),
    (
        "anywhere in the US",
        re.compile(r"\banywhere\s+in\s+the\s+(?:u\.?s\.?|united states)\b", re.I),
    ),
    (
        "US work authorization",
        re.compile(
            r"\bauthori[sz]ed\s+to\s+work\s+in\s+(?:the\s+)?(?:u\.?s\.?|united states)\b",
            re.I,
        ),
    ),
    ("E-Verify", re.compile(r"\be[- ]?verify\b", re.I)),
    (
        "US residency",
        re.compile(
            r"\bmust\s+(?:reside|live|be located|be based)\s+in\s+(?:the\s+)?(?:u\.?s\.?|usa|united states)\b",
            re.I,
        ),
    ),
    (
        "US requisition",
        re.compile(
            r"\b(?:requisition|position|role)\b[^.\n]{0,80}\b(?:within|in)\s+(?:the\s+)?(?:u\.?s\.?|united states)\b",
            re.I,
        ),
    ),
)

_POSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("work from anywhere", re.compile(r"\bwork\s+from\s+anywhere\b", re.I)),
    ("global remote", re.compile(r"\bglobal\s+remote\b", re.I)),
    ("remote worldwide", re.compile(r"\bremote\s+worldwide\b|\bworldwide\s+remote\b", re.I)),
    ("international contractor", re.compile(r"\binternational\s+contractor\b", re.I)),
    (
        "country of residence",
        re.compile(
            r"\b(?:contract|contracts|employment|engagement|engaged|hire|hiring)[^.\n]{0,100}\bcountry\s+of\s+residence\b|\bcountry\s+of\s+residence\b[^.\n]{0,100}\b(?:contract|employment|engagement|hire|hiring)\b",
            re.I,
        ),
    ),
)

_US_LOCATION_PATTERN = re.compile(
    r"\b(?:united states(?: of america)?|usa|u\.s\.|u\.s\.a\.)\b", re.I
)


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def analyze_location_evidence(*, location: str, source_text: str) -> LocationEvidenceResult:
    """Extract explicit hiring-geography evidence without performing fit analysis.

    Explicit restrictive evidence wins over generic Remote labels. Positive evidence is
    intentionally limited to hiring/employment language; phrases such as "global company"
    or "international team" are not treated as eligibility evidence.
    """

    combined = "\n".join(part for part in (location, source_text) if part)
    negative: list[str] = []
    positive: list[str] = []

    for label, pattern in _NEGATIVE_PATTERNS:
        match = pattern.search(combined)
        if match:
            negative.append(match.group(0) or label)

    location_scope = normalized_location_scope(location)
    if location_scope == "foreign_country" and _US_LOCATION_PATTERN.search(location):
        negative.append(location)

    for label, pattern in _POSITIVE_PATTERNS:
        match = pattern.search(combined)
        if match:
            positive.append(match.group(0) or label)

    # Location metadata itself is authoritative evidence when it explicitly names a
    # Spain-compatible hiring scope. This is deliberately narrower than searching the
    # whole advert for words such as "global" or "Europe".
    if location_scope in {"spain", "broad"}:
        positive.append(location)

    negative_evidence = _unique(negative)
    positive_evidence = _unique(positive)

    if negative_evidence:
        return LocationEvidenceResult(
            location_eligibility="ineligible",
            hardline_reject=True,
            positive_evidence=positive_evidence,
            negative_evidence=negative_evidence,
        )

    if positive_evidence:
        return LocationEvidenceResult(
            location_eligibility="eligible",
            hardline_reject=False,
            positive_evidence=positive_evidence,
            negative_evidence=(),
        )

    return LocationEvidenceResult(
        location_eligibility="conditional",
        hardline_reject=False,
        positive_evidence=(),
        negative_evidence=(),
    )
