"""Read-only evidence preparation for JOLT AI export.

Advisory only: never decides suitability or writes to the database.
All candidate requirements preserve verbatim source text.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

VERSION = "1.0"
_REQUIRED = re.compile(
    r"\b(?:must have|required|requirements?|essential|mandatory|"
    r"you (?:need|must)|requisitos?|imprescindible|obligatorio|"
    r"se requiere|se exige|necesario|experiencia (?:en|con))\b",
    re.IGNORECASE,
)
_PREFERRED = re.compile(
    r"\b(?:nice to have|preferred|desirable|a plus|bonus|"
    r"valorable|deseable|se valorará|preferible)\b",
    re.IGNORECASE,
)
_COMMERCIAL = re.compile(
    r"\b(?:door.to.door|cold calling|cold sales|"
    r"venta puerta a puerta|puerta fría|captación a puerta fría)\b",
    re.IGNORECASE,
)


def _requirement_candidates(text: str) -> list[dict[str, str | bool]]:
    seen: set[str] = set()
    result: list[dict[str, str | bool]] = []
    for line in text.splitlines():
        for chunk in re.split(r"(?<=[.!?;])\s+", line.strip()):
            chunk = re.sub(r"\s+", " ", chunk).strip(" -•\t")
            if not chunk or len(chunk) > 340:
                continue
            preferred = _PREFERRED.search(chunk)
            required = _REQUIRED.search(chunk)
            if not (preferred or required) or chunk.casefold() in seen:
                continue
            seen.add(chunk.casefold())
            result.append(
                {
                    "requirement": chunk,
                    "source_text": chunk,
                    "classification_candidate": "preferred" if preferred else "required",
                    "candidate_match": "unknown",
                    "verification_required": True,
                }
            )
            if len(result) == 24:
                return result
    return result


def build_job_preanalysis(
    *,
    title: str,
    description: str,
    location: str,
    location_evidence: Any,
    language_evidence: Any,
) -> dict[str, Any]:
    """Build stable advisory signals using the existing JOLT analyzers."""
    source_text = description or ""
    geo = getattr(location_evidence, "location_eligibility", "unknown")
    requirements = _requirement_candidates(source_text)
    commercial_evidence = [
        line.strip()[:340] for line in source_text.splitlines() if _COMMERCIAL.search(line)
    ][:5]
    uncertainties = []
    if not source_text.strip():
        uncertainties.append("Captured description is empty")
    if geo in ("conditional", "unknown"):
        uncertainties.append("Employment territory or on-site requirement unresolved")
    if not requirements:
        uncertainties.append("No explicit requirement markers extracted")
    if commercial_evidence:
        uncertainties.append("Commercial work signal needs contextual evaluation")
    return {
        "version": VERSION,
        "authority": "advisory_only",
        "input_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "title": title,
        "location": location,
        "language": language_evidence.as_dict(),
        "geography": {
            "location_eligibility": geo,
            "hardline_reject": bool(getattr(location_evidence, "hardline_reject", False)),
            "positive_evidence": list(getattr(location_evidence, "positive_evidence", ())),
            "negative_evidence": list(getattr(location_evidence, "negative_evidence", ())),
        },
        "requirement_candidates": requirements,
        "commercial_exclusion_signals": commercial_evidence,
        "uncertainties": uncertainties,
        "final_decision": None,
        "review_required": True,
    }
