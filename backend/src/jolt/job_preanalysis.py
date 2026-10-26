"""Read-only evidence preparation for JOLT AI export.

Advisory only: never decides suitability or writes to the database.
All candidate requirements preserve verbatim source text.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

VERSION = "1.1"
_REQUIRED = re.compile(
    r"\b(?:must have|required|requirements?|essential|mandatory|"
    r"you (?:need|must)|requisitos?|imprescindible|obligatorio|"
    r"se requiere|se exige|necesario|experiencia (?:en|con)|"
    r"proficiency in|knowledge of|familiarity with|proven experience|"
    r"\d+\+? years? of experience|conocimientos? (?:de|en)|dominio de)\b",
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

_REQUIRED_SECTION = re.compile(
    r"^(?:requirements?|required qualifications?|minimum qualifications?|"
    r"your qualifications?|what you (?:bring|need)|about you|who you are|"
    r"requisitos(?: del puesto)?|perfil(?: requerido| buscado)?|"
    r"conocimientos requeridos|formación y experiencia)\s*:?$",
    re.IGNORECASE,
)
_PREFERRED_SECTION = re.compile(
    r"^(?:preferred qualifications?|nice to have|nice.to.haves|"
    r"desirable skills?|valorable|se valorará|deseable)\s*:?$",
    re.IGNORECASE,
)
_OTHER_SECTION = re.compile(
    r"^(?:responsibilities|your responsibilities|key responsibilities|"
    r"what you(?:'ll| will) do|your role|about us|benefits|what we offer|"
    r"funciones|tareas|responsabilidades|qué harás|qué ofrecemos|"
    r"beneficios|condiciones|descripción del puesto)\s*:?$",
    re.IGNORECASE,
)


def _requirement_candidates(text: str) -> list[dict[str, str | bool]]:
    """Extract source-backed candidate requirements, preserving section context."""
    seen: set[str] = set()
    result: list[dict[str, str | bool]] = []
    section: str | None = None
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" -•*\t")
        if not line:
            continue
        if _PREFERRED_SECTION.fullmatch(line):
            section = "preferred"
            continue
        if _REQUIRED_SECTION.fullmatch(line):
            section = "required"
            continue
        if _OTHER_SECTION.fullmatch(line):
            section = None
            continue
        if line.endswith(":") and len(line) < 65 and not _REQUIRED.search(line):
            section = None
            continue
        parts = re.split(r"(?<=[.!?;])\s+", line) if len(line) > 340 else [line]
        for chunk in parts:
            chunk = chunk.strip()
            if not 9 <= len(chunk) <= 440:
                continue
            preferred = bool(_PREFERRED.search(chunk))
            required = bool(_REQUIRED.search(chunk))
            if not (preferred or required or section):
                continue
            key = chunk.casefold()
            if key in seen:
                continue
            seen.add(key)
            classification = (
                "preferred"
                if preferred or (section == "preferred" and not required)
                else "required"
            )
            result.append(
                {
                    "requirement": chunk,
                    "source_text": chunk,
                    "classification_candidate": classification,
                    "candidate_match": "unknown",
                    "verification_required": True,
                }
            )
            if len(result) >= 36:
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
