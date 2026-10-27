"""Read-only, bounded dossiers for AI Work Package review.

Evidence hits are *mentions*, never verified professional skills or decisions.
The authoritative vacancy text and existing review contract remain unchanged.
"""

from __future__ import annotations

import re
from typing import Any

DOSSIER_VERSION = "1.1"

SKILLS = {
    "sql": (r"\bsql\b",),
    "python": (r"\bpython\b",),
    "powershell": (r"\bpowershell\b",),
    "windows": (r"\bwindows\b(?!\s+forms\b)",),
    "microsoft 365": (r"\b(?:microsoft 365|m365|office 365)\b",),
    "active directory": (r"\b(?:active directory|active directory domain services|ad ds)\b",),
    "entra id": (r"\b(?:entra id|azure ad)\b",),
    "intune": (r"\bintune\b",),
    "azure": (r"\bazure\b",),
    "aws": (r"\baws\b",),
    "linux": (r"\blinux\b",),
    "sap": (r"\bsap\b",),
    "vmware": (r"\b(?:vmware|vsphere|esxi)\b",),
    "networking": (r"\b(?:networking|tcp/ip|dns|dhcp)\b",),
    "rest api": (r"\b(?:rest api|restful api)\b",),
    "itil": (r"\bitil\b",),
    "servicenow": (r"\bservicenow\b",),
    "jira": (r"\bjira\b",),
    "customer support": (r"\b(?:customer support|atención al cliente)\b",),
    "excel": (r"\bexcel\b",),
    "salesforce": (r"\bsalesforce\b",),
}

REMOTE = re.compile(r"\b(?:remote|remoto|teletrabajo|work from home|wfh)\b", re.I)
ONSITE = re.compile(
    r"\b(?:on.site|on site|presencial|office days?|days? (?:per|a) week in (?:the )?office|"
    r"d[ií]as? (?:por|a la) semana (?:en|de) (?:la )?oficina)\b",
    re.I,
)
HYBRID = re.compile(r"\b(?:hybrid|h[ií]brido)\b", re.I)
EXPLICIT_VIGO = re.compile(r"\b(?:vigo|porriño|mos|redondela|nigr[aá]n|baiona)\b", re.I)
NONLOCAL = re.compile(r"\b(?:madrid|barcelona|valladolid|valencia|sevilla|bilbao|zaragoza)\b", re.I)


def _mentioned_skills(text: str) -> list[str]:
    return [
        skill
        for skill, patterns in SKILLS.items()
        if any(re.search(pattern, text, re.I) for pattern in patterns)
    ]


def _candidate_indexes(ledger: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Cite bounded source lines, not whole-page keyword co-occurrence."""
    index: dict[str, list[dict[str, str]]] = {}
    for source in ledger.get("source_evidence", []):
        if not isinstance(source, dict):
            continue
        title = str(source.get("title", "")).casefold()
        if title not in {"experience", "skills", "licenses & certifications"}:
            continue
        ref = source.get("evidence_ref")
        if not isinstance(ref, str) or not ref:
            continue
        lines = str(source.get("visible_text", "")).splitlines()
        for line in lines:
            snippet = line.strip()
            if not snippet or len(snippet) > 500:
                continue
            for skill in _mentioned_skills(snippet):
                records = index.setdefault(skill, [])
                if any(item["source_text"] == snippet for item in records):
                    continue
                if len(records) >= 5:
                    continue
                records.append(
                    {
                        "evidence_ref": ref,
                        "source_section": title,
                        "source_text": snippet[:240],
                        "claim_status": "unverified_mention",
                    }
                )
    return index

def _work_model_conflicts(text: str, location: str) -> list[str]:
    """Indicate contradictions, not employment eligibility decisions."""
    signals = []
    if REMOTE.search(text) and ONSITE.search(text) and not HYBRID.search(text):
        signals.append("remote_and_office_presence_language")
    if REMOTE.search(text) and NONLOCAL.search(text) and not EXPLICIT_VIGO.search(text):
        signals.append("remote_territory_or_nonlocal_location_requires_verification")
    if NONLOCAL.search(location) and not EXPLICIT_VIGO.search(location):
        signals.append("nonlocal_posting_location_requires_work_model_verification")
    return signals


def enrich_review_inbox_with_dossiers(
    inbox: dict[str, Any] | None,
    candidate_evidence: dict[str, Any],
) -> dict[str, Any] | None:
    """Add bounded, provenance-aware hints to existing AI review jobs."""
    if inbox is None:
        return None
    index = _candidate_indexes(candidate_evidence)
    jobs = inbox.get("jobs")
    if not isinstance(jobs, list):
        return inbox
    unresolved = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        pre = job.get("preanalysis")
        pre = pre if isinstance(pre, dict) else {}
        requirements = pre.get("requirement_candidates", [])
        requirements = requirements if isinstance(requirements, list) else []
        matched = []
        for item in requirements[:36]:
            if not isinstance(item, dict):
                continue
            evidence = str(item.get("source_text", ""))
            skills = _mentioned_skills(evidence)
            if not skills:
                continue
            matched.append(
                {
                    "source_text": evidence,
                    "classification_candidate": item.get("classification_candidate", "unknown"),
                    "skills": skills,
                    "candidate_mentions": {skill: index.get(skill, [])[:3] for skill in skills},
                    "assessment": "ai_verification_required",
                    "evidence_type": "source_excerpt_not_professional_validation",
                }
            )
        text = str(job.get("analysis_text", ""))
        conflicts = _work_model_conflicts(text, str(job.get("location", "")))
        missing = len(requirements) == 0
        if missing:
            unresolved += 1
        job["evaluation_dossier"] = {
            "version": DOSSIER_VERSION,
            "authority": "advisory_only",
            "requirement_skill_crosswalk": matched,
            "work_model_warnings": conflicts,
            "requirements_not_extracted": missing,
            "priority_for_ai": (
                "high" if missing or conflicts or pre.get("uncertainties") else "normal"
            ),
            "human_or_ai_checks": [
                "Validate mandatory requirements against verbatim vacancy text",
                "Verify employer-controlled source and Spain work eligibility",
                "Do not promote profile mentions, courses or projects into production experience",
            ],
            "final_decision": None,
        }
    inbox["dossier_metadata"] = {
        "version": DOSSIER_VERSION,
        "jobs_enriched": sum(isinstance(job, dict) and "evaluation_dossier" in job for job in jobs),
        "jobs_without_extracted_requirements": unresolved,
        "decision_authority": "external_ai",
    }
    return inbox
