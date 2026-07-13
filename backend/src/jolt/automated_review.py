from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Evaluation, Posting, ProfileVersion, utc_now

PROFILE_ID = "rafael-job-search"
PROFILE_VERSION_ID = "rafael-job-search:v2"
ENGINE_VERSION = "profile-rules-v2"

PROFILE_CONFIGURATION: dict[str, Any] = {
    "candidate": "Rafael Alba",
    "base_location": "Spain",
    "languages": ["English", "Spanish"],
    "target_roles": [
        "application support",
        "production support",
        "technical support engineer",
        "software support",
        "infrastructure support",
        "it operations",
        "service desk level 2",
        "systems support",
    ],
    "strong_evidence": {
        "support_ownership": [
            "incident ownership",
            "incident management",
            "troubleshooting",
            "root cause",
            "escalation",
            "production support",
        ],
        "application_support": [
            "application support",
            "software support",
            "logs",
            "api",
            "integration",
            "sql",
            "database",
        ],
        "infrastructure": [
            "microsoft 365",
            "entra id",
            "azure ad",
            "windows",
            "dns",
            "networking",
            "vmware",
            "backup",
            "infrastructure",
        ],
        "operations": [
            "it operations",
            "production environment",
            "manufacturing",
            "mes",
            "runbook",
            "documentation",
            "on-call",
            "monitoring",
        ],
        "automation": ["powershell", "automation", "python", "scripting"],
    },
    "development_heavy": [
        "full stack developer",
        "software developer",
        "software engineer",
        "frontend developer",
        "backend developer",
        "build new features",
        "design and implement software",
    ],
    "management_heavy": [
        "people manager",
        "direct reports",
        "performance reviews",
        "manage a team of",
        "head of",
    ],
    "hard_blockers": [
        "mandatory german",
        "german is mandatory",
        "must speak german",
        "native german",
        "mandatory french",
        "french is mandatory",
        "must speak french",
        "native french",
    ],
    "uncertainty_terms": {
        "salary": ["salary", "compensation", "pay range"],
        "contract": ["contract", "permanent", "freelance", "b2b"],
        "remote_eligibility": ["remote", "hybrid", "on-site", "onsite"],
        "shift_on_call": ["shift", "on-call", "24/7", "weekend"],
        "travel": ["travel", "onsite visits"],
    },
}


@dataclass(frozen=True)
class ReviewAnalysis:
    recommendation: str
    proposed_decision: str
    confidence: str
    score: int
    summary: str
    strengths: list[str]
    gaps: list[str]
    blockers: list[str]
    uncertainties: list[str]
    dimensions: dict[str, int]

    @property
    def reasons(self) -> list[str]:
        reasons = [self.summary]
        reasons.extend(f"Strength: {item}" for item in self.strengths)
        reasons.extend(f"Gap: {item}" for item in self.gaps)
        reasons.extend(f"Blocker: {item}" for item in self.blockers)
        reasons.extend(f"Uncertainty: {item}" for item in self.uncertainties)
        return reasons


def _contains_any(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in text]


def _dimension_score(text: str, terms: list[str], weight: int) -> tuple[int, list[str]]:
    matches = _contains_any(text, terms)
    if not matches:
        return 0, matches
    per_match = max(7, (weight + 2) // 3)
    return min(weight, len(matches) * per_match), matches


def analyze_posting(title: str, location: str, description: str) -> ReviewAnalysis:
    text = "\n".join([title, location, description]).lower()
    blockers = _contains_any(text, PROFILE_CONFIGURATION["hard_blockers"])
    dimensions: dict[str, int] = {}
    strengths: list[str] = []
    weights = {
        "role_alignment": 25,
        "support_ownership": 20,
        "application_support": 20,
        "infrastructure": 15,
        "operations": 12,
        "automation": 8,
    }

    target_score, target_matches = _dimension_score(
        text, PROFILE_CONFIGURATION["target_roles"], weights["role_alignment"]
    )
    if target_matches:
        target_score = max(target_score, 18)
        strengths.append(f"Target-role alignment: {', '.join(target_matches[:3])}.")
    dimensions["role_alignment"] = target_score

    for dimension in [
        "support_ownership",
        "application_support",
        "infrastructure",
        "operations",
        "automation",
    ]:
        dimension_score, matches = _dimension_score(
            text,
            PROFILE_CONFIGURATION["strong_evidence"][dimension],
            weights[dimension],
        )
        dimensions[dimension] = dimension_score
        if matches:
            strengths.append(f"{dimension.replace('_', ' ').title()}: {', '.join(matches[:4])}.")

    score = sum(dimensions.values())
    gaps: list[str] = []
    development_matches = _contains_any(text, PROFILE_CONFIGURATION["development_heavy"])
    management_matches = _contains_any(text, PROFILE_CONFIGURATION["management_heavy"])

    if development_matches:
        score -= 24
        gaps.append("The role appears development-heavy rather than support-focused.")
    if management_matches:
        score -= 15
        gaps.append("The role may require formal people-management responsibility.")
    if not target_matches:
        gaps.append("The title and description do not clearly match Rafael's target support roles.")
    if dimensions["support_ownership"] == 0:
        gaps.append("No clear evidence of troubleshooting or incident ownership was found.")
    if dimensions["application_support"] == 0 and dimensions["infrastructure"] == 0:
        gaps.append("No strong application-support or infrastructure evidence was found.")

    uncertainties: list[str] = []
    uncertainty_terms = PROFILE_CONFIGURATION["uncertainty_terms"]
    if not _contains_any(text, uncertainty_terms["salary"]):
        uncertainties.append("Salary or compensation is not evidenced.")
    if not _contains_any(text, uncertainty_terms["contract"]):
        uncertainties.append("Contract type is not evidenced.")
    if not _contains_any(text, uncertainty_terms["remote_eligibility"]):
        uncertainties.append("Remote or location eligibility from Spain is unclear.")
    if _contains_any(text, uncertainty_terms["shift_on_call"]):
        uncertainties.append("Shift or on-call expectations require human confirmation.")
    if _contains_any(text, uncertainty_terms["travel"]):
        uncertainties.append("Travel expectations require human confirmation.")

    score = max(0, min(100, score))
    if blockers:
        recommendation = "reject"
        proposed_decision = "reject"
        confidence = "high"
        summary = "Automatic review found a verified language blocker."
    elif score >= 50 and not development_matches:
        recommendation = "pursue"
        proposed_decision = "pursue" if len(uncertainties) <= 2 else "consider"
        confidence = "high" if score >= 75 else "medium"
        summary = "Strong evidence-based alignment with Rafael's support and operations profile."
    elif score >= 32:
        recommendation = "consider"
        proposed_decision = "needs_more_information" if len(uncertainties) >= 3 else "consider"
        confidence = "medium"
        summary = "Partial alignment exists, but important fit evidence is missing or mixed."
    else:
        recommendation = "reject" if development_matches else "consider"
        proposed_decision = "reject" if development_matches else "needs_more_information"
        confidence = "medium" if development_matches else "low"
        summary = "Current evidence does not show enough alignment for a confident pursue decision."

    return ReviewAnalysis(
        recommendation=recommendation,
        proposed_decision=proposed_decision,
        confidence=confidence,
        score=score,
        summary=summary,
        strengths=strengths,
        gaps=gaps,
        blockers=[f"Verified phrase: {item}." for item in blockers],
        uncertainties=uncertainties,
        dimensions=dimensions,
    )


def ensure_profile(session: Session) -> ProfileVersion:
    profile = session.get(ProfileVersion, PROFILE_VERSION_ID)
    if profile is not None:
        return profile
    profile = ProfileVersion(
        id=PROFILE_VERSION_ID,
        profile_id=PROFILE_ID,
        version=2,
        configuration_json=json.dumps(PROFILE_CONFIGURATION, sort_keys=True),
        created_at=utc_now(),
    )
    session.add(profile)
    session.flush()
    return profile


def ensure_automated_reviews(session: Session) -> None:
    profile = ensure_profile(session)
    postings = session.scalars(select(Posting)).all()
    changed = False
    for posting in postings:
        latest = session.scalar(
            select(Evaluation)
            .where(Evaluation.posting_id == posting.id)
            .order_by(Evaluation.created_at.desc())
        )
        if latest is not None and latest.engine_version == ENGINE_VERSION:
            continue
        analysis = analyze_posting(posting.title, posting.location, posting.description)
        session.add(
            Evaluation(
                id=str(uuid4()),
                posting_id=posting.id,
                profile_version_id=profile.id,
                engine_version=ENGINE_VERSION,
                recommendation=analysis.recommendation,
                confidence=analysis.confidence,
                ranking_score=analysis.score,
                reasons_json=json.dumps(analysis.reasons),
                created_at=utc_now(),
            )
        )
        changed = True
    if changed:
        session.commit()
