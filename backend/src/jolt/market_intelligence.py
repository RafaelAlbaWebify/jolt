from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import (
    Evaluation,
    MarketIntelligenceObservation,
    Posting,
    SourceDocument,
)
from jolt.semantic_duplicates import group_semantic_duplicates
from jolt.strategy_runtime import ENGINE_VERSION

_REQUIRED_SKILL_MARKERS = (
    "requirements:",
    "required",
    "must have",
    "must-have",
    "mandatory",
    "essential",
    "demonstrable experience",
    "proven experience",
    "hands-on experience",
)

_PREFERRED_SKILL_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "desirable",
    "advantage",
    "bonus",
    "ideally",
)

SKILL_TERMS = (
    "active directory",
    "azure",
    "aws",
    "linux",
    "windows",
    "sql",
    "python",
    "powershell",
    "rest api",
    "api",
    "saas",
    "servicenow",
    "jira",
    "docker",
    "kubernetes",
    "microsoft 365",
    "office 365",
    "networking",
    "dns",
    "dhcp",
    "vmware",
    "itil",
    "splunk",
    "grafana",
    "datadog",
)


def _skill_label(skill: str) -> str:
    if skill in {"sql", "aws", "dns", "dhcp", "api"}:
        return skill.upper()
    return skill.title()


def _skill_evidence(text: str) -> dict[str, int]:
    evidence: dict[str, int] = {}

    for fragment in re.split(r"[\n.;•]+", text.lower()):
        fragment = fragment.strip()
        if not fragment:
            continue

        strength = 0
        if any(marker in fragment for marker in _PREFERRED_SKILL_MARKERS):
            strength = 1
        if any(marker in fragment for marker in _REQUIRED_SKILL_MARKERS):
            strength = 2

        for skill in SKILL_TERMS:
            if skill not in fragment:
                continue

            label = _skill_label(skill)
            evidence[label] = max(evidence.get(label, 0), strength)

    return evidence


TARGET_ROLE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Application support",
        (
            "application support",
            "application analyst",
            "business application",
            "enterprise application",
            "soporte aplicaciones",
            "soporte de aplicaciones",
            "tecnico n2 soporte aplicaciones",
            "soporte bbdd sql",
            "pi system soporte",
        ),
    ),
    (
        "Production support",
        (
            "production support",
            "production operations",
            "site reliability",
            " sre ",
            "noc engineer",
            "operations support",
        ),
    ),
    (
        "Technical / product support",
        (
            "technical support",
            "support engineer",
            "tech support",
            "product support",
            "technical customer support",
            "technischer kunden support",
            "soporte tecnico",
            "tecnico soporte",
            "software support",
            "solutions support",
            "customer technical",
            "support specialist",
        ),
    ),
    (
        "Service desk / workplace support",
        (
            "service desk",
            "help desk",
            "helpdesk",
            "it support",
            "desktop support",
            "deskside",
            "workplace support",
            "end user support",
            "2nd line support",
            "second line support",
            "3rd level support",
            "it maintenance and support",
        ),
    ),
    (
        "Cloud / infrastructure operations",
        (
            "cloud operations",
            "cloud support",
            "infrastructure support",
            "infrastructure engineer",
            "systems administrator",
            "system administrator",
            "sysadmin",
            "network support",
            "platform operations",
            "azure cloud engineer",
        ),
    ),
    (
        "IT service management",
        (
            "service manager",
            "service delivery",
            "incident manager",
            "problem manager",
            "change manager",
            "it operations manager",
        ),
    ),
)

_DECISION_BANDS = (
    "Actionable strong match",
    "Actionable viable match",
    "Conditional / preparation needed",
    "Manual review needed",
    "Blocked / do not pursue",
)
_TECHNICAL_FIT_BANDS = (
    "Strong technical fit · 80–100",
    "Viable technical fit · 60–79",
    "Stretch technical fit · 40–59",
    "Low technical fit · 0–39",
)
_BLOCKED_RECOMMENDATIONS = {"do_not_pursue", "reject"}


@dataclass(frozen=True)
class _DurableMarketPosting:
    id: str
    title: str
    company: str
    location: str
    description: str
    created_at: datetime


@dataclass(frozen=True)
class _DurableMarketEvaluation:
    posting_id: str
    engine_version: str
    recommendation: str
    confidence: str
    ranking_score: int
    reasons_json: str


MarketPosting = Posting | _DurableMarketPosting
MarketEvaluation = Evaluation | _DurableMarketEvaluation


def _normalized_title(title: str) -> str:
    return f" {re.sub(r'[^a-z0-9]+', ' ', title.lower()).strip()} "


def _role_family(title: str) -> tuple[str, bool]:
    value = _normalized_title(title)
    for family, patterns in TARGET_ROLE_PATTERNS:
        if any(pattern in value for pattern in patterns):
            return family, True
    return "Outside target support roles", False


def _work_mode(location: str, description: str) -> str:
    value = f"{location} {description}".lower()
    if "hybrid" in value or "híbrido" in value:
        return "Hybrid"
    if "remote" in value or "remoto" in value:
        return "Remote"
    return "Onsite / unspecified"


def _seniority(title: str) -> str:
    value = _normalized_title(title)
    if any(term in value for term in (" lead ", " principal ", " manager ", " head ")):
        return "Lead / management"
    if any(term in value for term in (" senior ", " sr ", " level 3 ", " l3 ")):
        return "Senior"
    if any(term in value for term in (" junior ", " jr ", " entry ", " intern ")):
        return "Junior / internship"
    return "Mid / unspecified"


def _salary_mentions(text: str) -> list[str]:
    patterns = (
        r"(?:€|eur\s*)\s?\d{2,3}(?:[.,]\d{3})(?:\s?[-–]\s?(?:€|eur\s*)?\s?\d{2,3}(?:[.,]\d{3}))?",
        r"\d{2,3}(?:[.,]\d{3})\s?(?:€|eur)(?:\s?[-–]\s?\d{2,3}(?:[.,]\d{3})\s?(?:€|eur))?",
        r"(?:€|eur\s*)\s?\d{2,3}(?:\.\d{3})?\s?(?:per year|annually|annual|yearly|\/year)",
    )
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return list(dict.fromkeys(match.strip() for match in matches if match.strip()))


def _assessment_payload(
    evaluation: MarketEvaluation | None,
) -> dict[str, Any]:
    if evaluation is None:
        return {}
    try:
        reasons = json.loads(evaluation.reasons_json)
    except json.JSONDecodeError:
        return {}
    prefix = "Strategy assessment JSON: "
    for reason in reversed(reasons):
        if isinstance(reason, str) and reason.startswith(prefix):
            try:
                payload = json.loads(reason[len(prefix) :])
                return payload if isinstance(payload, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _technical_fit_band(score: int) -> str:
    if score >= 80:
        return _TECHNICAL_FIT_BANDS[0]
    if score >= 60:
        return _TECHNICAL_FIT_BANDS[1]
    if score >= 40:
        return _TECHNICAL_FIT_BANDS[2]
    return _TECHNICAL_FIT_BANDS[3]


def _decision_band(recommendation: str) -> str:
    if recommendation == "strong_pursue":
        return _DECISION_BANDS[0]
    if recommendation in {"pursue", "apply"}:
        return _DECISION_BANDS[1]
    if recommendation in {"pursue_if_condition_met", "defer", "consider"}:
        return _DECISION_BANDS[2]
    if recommendation in _BLOCKED_RECOMMENDATIONS:
        return _DECISION_BANDS[4]
    return _DECISION_BANDS[3]


def _is_blocked(evaluation: MarketEvaluation) -> bool:
    assessment = _assessment_payload(evaluation)
    eligibility = assessment.get("eligibility")
    return evaluation.recommendation in _BLOCKED_RECOMMENDATIONS or eligibility == "ineligible"


def _ranked(counter: Counter[str], limit: int = 12) -> list[dict[str, object]]:
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


MARKET_BASELINE_LABEL = "Market Baseline v1 — 16 Aug 2026"
MARKET_BASELINE_AT = datetime(2026, 8, 16, 16, 26, tzinfo=UTC)


def _strings_under_evidence_keys(
    payload: object,
    key_markers: tuple[str, ...],
) -> list[str]:
    collected: list[str] = []

    def collect(value: object, active: bool = False) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key).casefold()
                child_active = active or any(marker in key_text for marker in key_markers)
                collect(child, child_active)
            return

        if isinstance(value, list):
            for child in value:
                collect(child, active)
            return

        if active and isinstance(value, str):
            collected.append(value)

    collect(payload)
    return collected


def _assessment_skill_labels(
    payload: dict[str, Any],
    key_markers: tuple[str, ...],
) -> set[str]:
    evidence_text = "\n".join(_strings_under_evidence_keys(payload, key_markers))
    if not evidence_text:
        return set()
    return set(_skill_evidence(evidence_text))


def _assessment_gap_skill_labels(
    payload: dict[str, Any],
) -> set[str]:
    raw_gaps = payload.get("gaps")
    if not isinstance(raw_gaps, list):
        return set()

    labels: set[str] = set()

    for gap in raw_gaps:
        evidence_parts: list[str] = []

        if isinstance(gap, str):
            evidence_parts.append(gap)

        if isinstance(gap, dict):
            label = gap.get("label")
            if isinstance(label, str):
                evidence_parts.append(label)

            matched_terms = gap.get("matched_terms")
            if isinstance(matched_terms, list):
                evidence_parts.extend(item for item in matched_terms if isinstance(item, str))

        if evidence_parts:
            labels.update(_skill_evidence("\n".join(evidence_parts)))

    return labels


def _capability_state(
    *,
    gap_count: int,
    strength_count: int,
) -> str:
    if gap_count and strength_count:
        return "partial"
    if gap_count:
        return "missing"
    if strength_count:
        return "covered"
    return "unknown"


def _interview_signal(
    *,
    demand: int,
    required: int,
    gap_count: int,
) -> str:
    if required >= 2 or (demand and required / demand >= 0.5):
        return "High"
    if required or gap_count >= 2:
        return "Medium"
    return "Low"


def _learning_signal_rows(
    *,
    skills: Counter[str],
    required_skills: Counter[str],
    preferred_skills: Counter[str],
    gap_skills: Counter[str],
    capability_gap_skills: Counter[str],
    strength_skills: Counter[str],
    skill_role_families: dict[str, Counter[str]],
    gap_shortfalls: dict[str, list[int]],
) -> list[dict[str, object]]:
    if not skills:
        return []

    max_demand = max(skills.values())
    family_universe = {
        family for family_counter in skill_role_families.values() for family in family_counter
    }
    max_families = max(1, len(family_universe))

    rows: list[dict[str, object]] = []

    for skill, demand in skills.items():
        required = required_skills.get(skill, 0)
        preferred = preferred_skills.get(skill, 0)
        gap_count = gap_skills.get(skill, 0)
        strength_count = strength_skills.get(skill, 0)
        families = skill_role_families.get(skill, Counter())
        role_family_count = len(families)

        shortfalls = gap_shortfalls.get(skill, [])
        avg_shortfall = round(sum(shortfalls) / len(shortfalls), 1) if shortfalls else None

        demand_component = demand / max_demand
        gap_component = min(gap_count / max(1, demand), 1.0)
        required_component = min(required / max(1, demand), 1.0)
        leverage_component = min(role_family_count / max_families, 1.0)
        shortfall_component = min(avg_shortfall / 40.0, 1.0) if avg_shortfall is not None else 0.0

        indicator = round(
            10
            * (
                0.25 * demand_component
                + 0.25 * gap_component
                + 0.25 * required_component
                + 0.15 * leverage_component
                + 0.10 * shortfall_component
            ),
            1,
        )

        rows.append(
            {
                "skill": skill,
                "demand": demand,
                "required_count": required,
                "preferred_count": preferred,
                "gap_count": gap_count,
                "average_fit_shortfall_proxy": avg_shortfall,
                "role_family_count": role_family_count,
                "role_family_split": [
                    {"label": label, "count": count} for label, count in families.most_common()
                ],
                "capability_state": _capability_state(
                    gap_count=capability_gap_skills.get(skill, 0),
                    strength_count=strength_count,
                ),
                "interview_signal": _interview_signal(
                    demand=demand,
                    required=required,
                    gap_count=gap_count,
                ),
                "preparation_hours": None,
                "trend": "baseline",
                "evidence_priority_indicator": indicator,
            }
        )

    def sort_key(row: dict[str, object]) -> tuple[float, int, int]:
        indicator_value = row.get("evidence_priority_indicator")
        required_value = row.get("required_count")
        demand_value = row.get("demand")

        indicator = float(indicator_value) if isinstance(indicator_value, (int, float)) else 0.0
        required = required_value if isinstance(required_value, int) else 0
        demand = demand_value if isinstance(demand_value, int) else 0

        return indicator, required, demand

    return sorted(
        rows,
        key=sort_key,
        reverse=True,
    )[:25]


def _learning_refresh_status(
    postings: list[MarketPosting],
) -> dict[str, object]:
    now = datetime.now(UTC)
    jobs_since_baseline = sum(
        1
        for posting in postings
        if (_as_aware(posting.created_at) or datetime.min.replace(tzinfo=UTC)) > MARKET_BASELINE_AT
    )
    days_since_baseline = max(
        0,
        (now.date() - MARKET_BASELINE_AT.date()).days,
    )

    reasons: list[str] = []
    if jobs_since_baseline >= 10:
        reasons.append("10_new_relevant_jobs")
    if days_since_baseline >= 7:
        reasons.append("weekly_refresh")

    return {
        "baseline_label": MARKET_BASELINE_LABEL,
        "baseline_at": MARKET_BASELINE_AT.isoformat(),
        "jobs_since_baseline": jobs_since_baseline,
        "days_since_baseline": days_since_baseline,
        "refresh_due": bool(reasons),
        "trigger_reasons": reasons,
        "policy": "Recalculate after 10 new relevant jobs or 7 days, whichever comes first.",
    }


def _manual_market_postings(
    session: Session,
) -> list[Posting]:
    return list(
        session.scalars(
            select(Posting)
            .join(
                SourceDocument,
                SourceDocument.id == Posting.source_document_id,
            )
            .where(SourceDocument.source_type == "manual")
            .order_by(Posting.created_at.desc())
        ).all()
    )


def _is_synthetic_audit_posting(posting: MarketPosting) -> bool:
    title = posting.title.casefold()
    company = posting.company.casefold()
    return (
        title.startswith("jolt daily workflow audit")
        or title.startswith("jolt stage reversal audit")
        or company in {"audit systems", "audit systems ltd"}
    )


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _filter_by_timeframe(
    postings: list[MarketPosting],
    timeframe: str,
) -> list[MarketPosting]:
    if timeframe == "last_7_days":
        threshold = datetime.now(UTC) - timedelta(days=7)
    elif timeframe == "last_30_days":
        threshold = datetime.now(UTC) - timedelta(days=30)
    else:
        return postings
    return [
        posting
        for posting in postings
        if (_as_aware(posting.created_at) or datetime.min.replace(tzinfo=UTC)) >= threshold
    ]


def _effective_evaluations(
    session: Session, postings: list[Posting]
) -> tuple[dict[str, Evaluation], dict[str, object]]:
    evaluations = list(
        session.scalars(select(Evaluation).order_by(Evaluation.created_at.desc())).all()
    )
    latest: dict[str, Evaluation] = {}
    current: dict[str, Evaluation] = {}
    for evaluation in evaluations:
        latest.setdefault(evaluation.posting_id, evaluation)
        if evaluation.engine_version == ENGINE_VERSION:
            current.setdefault(evaluation.posting_id, evaluation)

    effective: dict[str, Evaluation] = {}
    for posting in postings:
        evaluation = current.get(posting.id) or latest.get(posting.id)
        if evaluation is not None:
            effective[posting.id] = evaluation

    coverage = {
        "posting_count": len(postings),
        "evaluated_count": len(effective),
        "missing_count": len(postings) - len(effective),
        "current_engine_count": sum(1 for posting in postings if posting.id in current),
        "fallback_engine_count": sum(
            1 for posting in postings if posting.id in effective and posting.id not in current
        ),
        "current_engine": ENGINE_VERSION,
    }
    return effective, coverage


@dataclass(frozen=True)
class _MarketDuplicateCandidate:
    posting_id: str
    company: str
    title: str
    recommendation: str
    confidence: str
    ranking_score: int


def _deduplicate_market_postings(
    postings: list[MarketPosting],
    evaluations: dict[str, MarketEvaluation],
) -> tuple[list[MarketPosting], list[dict[str, object]]]:
    posting_by_id = {posting.id: posting for posting in postings}
    descriptions = {posting.id: posting.description or "" for posting in postings}

    candidates: list[_MarketDuplicateCandidate] = []
    for posting in postings:
        evaluation = evaluations.get(posting.id)
        candidates.append(
            _MarketDuplicateCandidate(
                posting_id=posting.id,
                company=posting.company,
                title=posting.title,
                recommendation=(
                    evaluation.recommendation if evaluation is not None else "review_manually"
                ),
                confidence=(evaluation.confidence if evaluation is not None else "low"),
                ranking_score=(evaluation.ranking_score if evaluation is not None else 0),
            )
        )

    groups = group_semantic_duplicates(
        candidates,
        descriptions=descriptions,
    )

    canonical_postings: list[MarketPosting] = []
    duplicate_groups: list[dict[str, object]] = []

    for group in groups:
        canonical_id = group[0].posting_id
        canonical_postings.append(posting_by_id[canonical_id])

        if len(group) > 1:
            member_ids = [member.posting_id for member in group]
            duplicate_groups.append(
                {
                    "canonical_posting_id": canonical_id,
                    "member_posting_ids": member_ids,
                    "duplicate_posting_ids": member_ids[1:],
                }
            )

    return canonical_postings, duplicate_groups


def _scope_data(
    postings: list[MarketPosting],
    evaluations: dict[str, MarketEvaluation],
) -> dict[str, object]:
    role_families: Counter[str] = Counter()
    work_modes: Counter[str] = Counter()
    seniority: Counter[str] = Counter()
    companies: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    required_skills: Counter[str] = Counter()
    preferred_skills: Counter[str] = Counter()
    mentioned_skills: Counter[str] = Counter()
    gap_skills: Counter[str] = Counter()
    capability_gap_skills: Counter[str] = Counter()
    strength_skills: Counter[str] = Counter()
    skill_role_families: dict[str, Counter[str]] = {}
    gap_shortfalls: dict[str, list[int]] = {}
    decision_bands: Counter[str] = Counter()
    technical_fit_bands: Counter[str] = Counter()
    salary_mentions: list[dict[str, str]] = []

    for posting in postings:
        family, _ = _role_family(posting.title)
        role_families[family] += 1
        work_modes[_work_mode(posting.location, posting.description)] += 1
        seniority[_seniority(posting.title)] += 1
        if posting.company:
            companies[posting.company] += 1
        if posting.location:
            locations[posting.location] += 1

        searchable = f"{posting.title}\n{posting.description}"
        posting_skill_evidence = _skill_evidence(searchable)

        for label, strength in posting_skill_evidence.items():
            skills[label] += 1
            family_counter = skill_role_families.setdefault(label, Counter())
            family_counter[family] += 1

            if strength == 2:
                required_skills[label] += 1
            if strength == 1:
                preferred_skills[label] += 1
            if strength == 0:
                mentioned_skills[label] += 1

        evaluation = evaluations.get(posting.id)
        if evaluation:
            technical_fit_bands[_technical_fit_band(evaluation.ranking_score)] += 1
            decision_bands[_decision_band(evaluation.recommendation)] += 1

            assessment = _assessment_payload(evaluation)

            gap_labels = _assessment_gap_skill_labels(assessment)
            gap_labels &= set(posting_skill_evidence)

            strength_labels = _assessment_skill_labels(
                assessment,
                ("strength", "demonstrated", "transferable", "capability"),
            )

            for label in gap_labels:
                capability_gap_skills[label] += 1

                if evaluation.ranking_score < 80:
                    gap_skills[label] += 1
                    gap_shortfalls.setdefault(label, []).append(80 - evaluation.ranking_score)

            for label in strength_labels:
                strength_skills[label] += 1

        mentions = _salary_mentions(posting.description)
        if mentions:
            salary_mentions.append(
                {
                    "title": posting.title,
                    "company": posting.company,
                    "mention": " · ".join(mentions),
                }
            )

    salary_role_count = len(salary_mentions)
    salary_coverage = salary_role_count / len(postings) if postings else 0.0

    return {
        "total_roles": len(postings),
        "blocked_roles": decision_bands.get(_DECISION_BANDS[4], 0),
        "review_roles": decision_bands.get(_DECISION_BANDS[2], 0)
        + decision_bands.get(_DECISION_BANDS[3], 0),
        "role_families": _ranked(role_families),
        "work_modes": _ranked(work_modes),
        "seniority": _ranked(seniority),
        "top_companies": _ranked(companies),
        "top_locations": _ranked(locations),
        "top_skills": _ranked(skills, 20),
        "required_skills": _ranked(required_skills, 20),
        "preferred_skills": _ranked(preferred_skills, 20),
        "mentioned_skills": _ranked(mentioned_skills, 20),
        "learning_signals": _learning_signal_rows(
            skills=skills,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            gap_skills=gap_skills,
            capability_gap_skills=capability_gap_skills,
            strength_skills=strength_skills,
            skill_role_families=skill_role_families,
            gap_shortfalls=gap_shortfalls,
        ),
        "learning_signal_explanation": (
            "This is an evidence indicator, not a career prescription. "
            "Demand, explicit requirement frequency, saved gap evidence, "
            "role-family spread and technical-fit shortfall are combined "
            "transparently. Preparation hours remain unavailable unless "
            "JOLT has retained evidence for them. Fit shortfall is a proxy "
            "to the 80-point technical-fit threshold, not an attributed "
            "per-skill penalty."
        ),
        "decision_distribution": [
            {"label": label, "count": decision_bands.get(label, 0)} for label in _DECISION_BANDS
        ],
        "technical_fit_distribution": [
            {"label": label, "count": technical_fit_bands.get(label, 0)}
            for label in _TECHNICAL_FIT_BANDS
        ],
        "salary_mentions": salary_mentions[:20],
        "salary_role_count": salary_role_count,
        "salary_coverage": salary_coverage,
        "salary_coverage_percent": round(salary_coverage * 100, 1),
    }


def _durable_capture_market_records(
    session: Session,
) -> tuple[
    list[_DurableMarketPosting],
    dict[str, _DurableMarketEvaluation],
]:
    observations = list(
        session.scalars(
            select(MarketIntelligenceObservation).order_by(
                MarketIntelligenceObservation.captured_at.desc(),
                MarketIntelligenceObservation.observed_at.desc(),
                MarketIntelligenceObservation.id.desc(),
            )
        ).all()
    )

    postings: list[_DurableMarketPosting] = []
    evaluations: dict[str, _DurableMarketEvaluation] = {}

    for observation in observations:
        posting = _DurableMarketPosting(
            id=observation.id,
            title=observation.title,
            company=observation.company,
            location=observation.location,
            description=observation.description,
            created_at=observation.captured_at,
        )
        postings.append(posting)

        if observation.recommendation and observation.ranking_score is not None:
            evaluations[posting.id] = _DurableMarketEvaluation(
                posting_id=posting.id,
                engine_version=observation.engine_version,
                recommendation=observation.recommendation,
                confidence=observation.confidence,
                ranking_score=observation.ranking_score,
                reasons_json=observation.reasons_json,
            )

    return postings, evaluations


def build_market_intelligence(
    session: Session,
    *,
    timeframe: str = "all",
    source_scope: str = "all",
) -> dict[str, object]:
    captured_postings, captured_evaluations = _durable_capture_market_records(session)

    manual_postings = _manual_market_postings(session)
    manual_evaluations, _ = _effective_evaluations(
        session,
        manual_postings,
    )

    if source_scope == "capture_batches":
        source_records: list[MarketPosting] = list(captured_postings)
        source_evaluations: dict[str, MarketEvaluation] = dict(captured_evaluations)
    elif source_scope == "manual_intake":
        source_records = list(manual_postings)
        source_evaluations = dict(manual_evaluations)
    else:
        source_records = [
            *captured_postings,
            *manual_postings,
        ]
        source_evaluations = {
            **captured_evaluations,
            **manual_evaluations,
        }

    active_records = list(source_records)
    production_records = [
        posting for posting in active_records if not _is_synthetic_audit_posting(posting)
    ]

    timeframe_records = _filter_by_timeframe(
        production_records,
        timeframe,
    )
    timeframe_ids = {posting.id for posting in timeframe_records}
    timeframe_evaluations = {
        posting_id: evaluation
        for posting_id, evaluation in source_evaluations.items()
        if posting_id in timeframe_ids
    }

    postings, duplicate_groups = _deduplicate_market_postings(
        timeframe_records,
        timeframe_evaluations,
    )
    canonical_ids = {posting.id for posting in postings}
    evaluations = {
        posting_id: evaluation
        for posting_id, evaluation in timeframe_evaluations.items()
        if posting_id in canonical_ids
    }

    current_engine_count = sum(
        1
        for evaluation in timeframe_evaluations.values()
        if evaluation.engine_version == ENGINE_VERSION
    )
    evaluated_count = len(timeframe_evaluations)

    evaluation_coverage = {
        "posting_count": len(timeframe_records),
        "evaluated_count": evaluated_count,
        "missing_count": len(timeframe_records) - evaluated_count,
        "current_engine_count": current_engine_count,
        "fallback_engine_count": (evaluated_count - current_engine_count),
        "current_engine": ENGINE_VERSION,
        "source_posting_count": len(timeframe_records),
        "canonical_role_count": len(postings),
        "duplicate_member_count": (len(timeframe_records) - len(postings)),
    }

    evidence_dates = [
        aware
        for posting in timeframe_records
        if (aware := _as_aware(posting.created_at)) is not None
    ]
    evidence_provenance = {
        "source_posting_count": len(timeframe_records),
        "canonical_role_count": len(postings),
        "duplicate_member_count": (len(timeframe_records) - len(postings)),
        "oldest_evidence_at": min(evidence_dates).isoformat() if evidence_dates else None,
        "newest_evidence_at": max(evidence_dates).isoformat() if evidence_dates else None,
    }

    target_postings: list[MarketPosting] = []
    outside_postings: list[MarketPosting] = []
    outside_titles: Counter[str] = Counter()

    for posting in postings:
        _, is_target = _role_family(posting.title)
        if is_target:
            target_postings.append(posting)
        else:
            outside_postings.append(posting)
            outside_titles[posting.title] += 1

    return {
        "filters": {
            "timeframe": timeframe,
            "source_scope": source_scope,
        },
        "total_unique_roles": len(postings),
        "target_role_count": len(target_postings),
        "outside_target_count": len(outside_postings),
        "target": _scope_data(
            target_postings,
            evaluations,
        ),
        "all": _scope_data(
            postings,
            evaluations,
        ),
        "evaluation_coverage": evaluation_coverage,
        "evidence_provenance": evidence_provenance,
        "learning_refresh": _learning_refresh_status(target_postings),
        "duplicate_groups": duplicate_groups,
        "excluded_synthetic_count": (len(active_records) - len(production_records)),
        "outside_title_examples": _ranked(
            outside_titles,
            15,
        ),
        "fit_explanation": (
            "Captured-job Market Intelligence is read from durable "
            "per-capture observations rather than historical raw capture "
            "batches. Exact repeated vacancy identities and semantic "
            "duplicates are collapsed for the aggregate unique-role view. "
            "Manual intake remains sourced from durable postings. "
            "Actionable fit combines the saved evaluation snapshot with "
            "eligibility and preferences; technical fit remains separate. "
            "Historical Market Intelligence therefore survives after "
            "superseded raw capture data is purged."
        ),
    }
