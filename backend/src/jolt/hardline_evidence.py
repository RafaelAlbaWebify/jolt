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


_US_STATE_NAMES = (
    "Alabama",
    "Alaska",
    "Arizona",
    "Arkansas",
    "California",
    "Colorado",
    "Connecticut",
    "Delaware",
    "Florida",
    "Georgia",
    "Hawaii",
    "Idaho",
    "Illinois",
    "Indiana",
    "Iowa",
    "Kansas",
    "Kentucky",
    "Louisiana",
    "Maine",
    "Maryland",
    "Massachusetts",
    "Michigan",
    "Minnesota",
    "Mississippi",
    "Missouri",
    "Montana",
    "Nebraska",
    "Nevada",
    "New Hampshire",
    "New Jersey",
    "New Mexico",
    "New York",
    "North Carolina",
    "North Dakota",
    "Ohio",
    "Oklahoma",
    "Oregon",
    "Pennsylvania",
    "Rhode Island",
    "South Carolina",
    "South Dakota",
    "Tennessee",
    "Texas",
    "Utah",
    "Vermont",
    "Virginia",
    "Washington",
    "West Virginia",
    "Wisconsin",
    "Wyoming",
    "District of Columbia",
)

# Keep abbreviations uppercase. Matching them case-insensitively creates dangerous
# collisions with ordinary words and non-English text: DE/de, IN/in, OR/or, ME/me, etc.
_US_STATE_ABBREVIATIONS = (
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
)

_US_STATE_NAME_PATTERN = "|".join(re.escape(value) for value in _US_STATE_NAMES)
_US_STATE_ABBREVIATION_PATTERN = "|".join(re.escape(value) for value in _US_STATE_ABBREVIATIONS)

_NEGATIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("US-only", re.compile(r"\b(?:u\.?s\.?|united states)\s+only\b", re.I)),
    (
        "US remote",
        re.compile(
            r"\b(?:u\.?s\.?|usa|united states)\s*(?:[-·|/]\s*)?remote\b|"
            r"\bremote\s*(?:[-·|/]\s*)?(?:usa|u\.?s\.?)\b",
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
            r"\bmust\s+(?:reside|live|be located|be based)\s+in\s+"
            r"(?:the\s+)?(?:u\.?s\.?|usa|united states)\b",
            re.I,
        ),
    ),
    (
        "US state-name residency",
        re.compile(
            rf"\bmust\s+(?:reside|live|be located|be based)\s+in\s+(?:the\s+)?(?:{_US_STATE_NAME_PATTERN})\b",
            re.I,
        ),
    ),
    (
        "US requisition",
        re.compile(
            r"\b(?:requisition|position|role)\b[^.\n]{0,80}\b(?:within|in)\s+"
            r"(?:the\s+)?(?:u\.?s\.?|united states)\b",
            re.I,
        ),
    ),
    (
        "US location",
        re.compile(
            r"\b(?:location|work location|based|located)\s*[:\-–—]?\s*"
            r"(?:the\s+)?(?:united states(?: of america)?|usa|u\.s\.)\b",
            re.I,
        ),
    ),
)

_POSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("work from anywhere", re.compile(r"\bwork\s+from\s+anywhere\b", re.I)),
    ("global remote", re.compile(r"\bglobal\s+remote\b", re.I)),
    (
        "remote worldwide",
        re.compile(r"\bremote\s+worldwide\b|\bworldwide\s+remote\b", re.I),
    ),
    ("international contractor", re.compile(r"\binternational\s+contractor\b", re.I)),
    (
        "country of residence",
        re.compile(
            r"\b(?:contract|contracts|employment|engagement|engaged|hire|hiring)"
            r"[^.\n]{0,100}\bcountry\s+of\s+residence\b|"
            r"\bcountry\s+of\s+residence\b[^.\n]{0,100}"
            r"\b(?:contract|employment|engagement|hire|hiring)\b",
            re.I,
        ),
    ),
    (
        "EMEA/Europe/Spain hiring",
        re.compile(
            r"\b(?:hire|hired|hiring|open|available|candidates?|position|role)\b"
            r"[^.\n]{0,100}\b(?:emea|europe|spain)\b|"
            r"\b(?:emea|europe|spain)\b[^.\n]{0,100}"
            r"\b(?:hire|hired|hiring|open|available|candidates?|position|role)\b",
            re.I,
        ),
    ),
)

_US_LOCATION_PATTERN = re.compile(
    r"\b(?:united states(?: of america)?|usa|u\.s\.|u\.s\.a\.)\b", re.I
)


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def _uppercase_state_abbreviation_after_comma(location: str) -> str | None:
    """Return a US state abbreviation only in canonical location syntax such as Austin, TX.

    Matching abbreviations with re.I is unsafe because several are common words in English
    or other languages. Requiring the original uppercase token after a comma keeps real US
    city/state locations detectable without treating `de`, `in`, `or`, `me`, etc. as states.
    """

    match = re.search(rf",\s*({_US_STATE_ABBREVIATION_PATTERN})(?:\b|$)", location)
    return match.group(1) if match else None


def _state_name_after_comma(location: str) -> str | None:
    """Return a full US state name only in canonical city/state location syntax."""

    match = re.search(rf",\s*({_US_STATE_NAME_PATTERN})(?:\b|$)", location, re.I)
    return match.group(1) if match else None


def _uppercase_state_abbreviation_in_residency(source_text: str) -> str | None:
    """Detect explicit residency wording such as 'must reside in TX' case-sensitively."""

    match = re.search(
        rf"\bmust\s+(?:reside|live|be located|be based)\s+in\s+(?:the\s+)?({_US_STATE_ABBREVIATION_PATTERN})\b",
        source_text,
        flags=0,
    )
    return match.group(0) if match else None


def analyze_location_evidence(*, location: str, source_text: str) -> LocationEvidenceResult:
    """Extract explicit hiring-geography evidence without performing fit analysis.

    Explicit restrictive evidence wins over generic Remote labels. Positive evidence is
    intentionally limited to hiring/employment language; phrases such as "global company",
    "international team", or "employees across Europe" are not eligibility evidence.
    """

    combined = "\n".join(part for part in (location, source_text) if part)
    negative: list[str] = []
    positive: list[str] = []

    for label, pattern in _NEGATIVE_PATTERNS:
        match = pattern.search(combined)
        if match:
            negative.append(match.group(0) or label)

    residency_abbreviation = _uppercase_state_abbreviation_in_residency(source_text)
    if residency_abbreviation:
        negative.append(residency_abbreviation)

    location_scope = normalized_location_scope(location)
    if location_scope == "foreign_country" and _US_LOCATION_PATTERN.search(location):
        negative.append(location)

    # A canonical US city/state location is a hardline signal. Abbreviations remain
    # case-sensitive to avoid ordinary-word collisions; full state names are safe to
    # match case-insensitively when they follow the city/state comma boundary.
    if not negative:
        state_name = _state_name_after_comma(location)
        state_abbreviation = _uppercase_state_abbreviation_after_comma(location)
        if state_name:
            negative.append(state_name)
        elif state_abbreviation:
            negative.append(state_abbreviation)

    for label, pattern in _POSITIVE_PATTERNS:
        match = pattern.search(combined)
        if match:
            positive.append(match.group(0) or label)

    # Location metadata itself is authoritative evidence when it explicitly names a
    # Spain-compatible hiring scope. Generic "Remote" remains ambiguous.
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
