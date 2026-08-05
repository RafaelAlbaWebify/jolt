from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_archival import ARCHIVED_CAPTURE_STATUS
from jolt.database import CaptureItem, CaptureRun, Evaluation, Posting
from jolt.strategy_runtime import ENGINE_VERSION

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


def _assessment_payload(evaluation: Evaluation | None) -> dict[str, Any]:
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


def _is_blocked(evaluation: Evaluation) -> bool:
    assessment = _assessment_payload(evaluation)
    eligibility = assessment.get("eligibility")
    return evaluation.recommendation in _BLOCKED_RECOMMENDATIONS or eligibility == "ineligible"


def _ranked(counter: Counter[str], limit: int = 12) -> list[dict[str, object]]:
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def _capture_statuses_by_posting(session: Session) -> dict[str, set[str]]:
    runs = {run.id: run for run in session.scalars(select(CaptureRun)).all()}
    statuses: dict[str, set[str]] = {}
    for item in session.scalars(
        select(CaptureItem).where(CaptureItem.posting_id.is_not(None))
    ).all():
        if not item.posting_id:
            continue
        run = runs.get(item.capture_run_id)
        if run is None:
            continue
        statuses.setdefault(item.posting_id, set()).add(run.status)
    return statuses


def _is_archived_capture_import(capture_statuses: set[str]) -> bool:
    return bool(capture_statuses) and all(
        status == ARCHIVED_CAPTURE_STATUS for status in capture_statuses
    )


def _is_synthetic_audit_posting(posting: Posting) -> bool:
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


def _filter_by_timeframe(postings: list[Posting], timeframe: str) -> list[Posting]:
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


def _filter_by_source_scope(
    postings: list[Posting], capture_statuses: dict[str, set[str]], source_scope: str
) -> list[Posting]:
    if source_scope == "capture_batches":
        return [posting for posting in postings if posting.id in capture_statuses]
    if source_scope == "manual_intake":
        return [posting for posting in postings if posting.id not in capture_statuses]
    return postings


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


def _scope_data(postings: list[Posting], evaluations: dict[str, Evaluation]) -> dict[str, object]:
    role_families: Counter[str] = Counter()
    work_modes: Counter[str] = Counter()
    seniority: Counter[str] = Counter()
    companies: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    decision_bands: Counter[str] = Counter()
    technical_fit_bands: Counter[str] = Counter()
    gaps: Counter[str] = Counter()
    study_topics: Counter[str] = Counter()
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

        searchable = f"{posting.title}\n{posting.description}".lower()
        for skill in SKILL_TERMS:
            if skill in searchable:
                label = (
                    skill.upper()
                    if skill in {"sql", "aws", "dns", "dhcp", "api"}
                    else skill.title()
                )
                skills[label] += 1

        evaluation = evaluations.get(posting.id)
        if evaluation:
            technical_fit_bands[_technical_fit_band(evaluation.ranking_score)] += 1
            decision_bands[_decision_band(evaluation.recommendation)] += 1
            if not _is_blocked(evaluation):
                assessment = _assessment_payload(evaluation)
                for gap in assessment.get("gaps", []):
                    if not isinstance(gap, dict):
                        continue
                    label = gap.get("label")
                    if isinstance(label, str) and label:
                        gaps[label] += 1
                    for topic in gap.get("preparation_topics", []):
                        if isinstance(topic, str) and topic:
                            study_topics[topic] += 1

        for mention in _salary_mentions(posting.description):
            salary_mentions.append(
                {"title": posting.title, "company": posting.company, "mention": mention}
            )

    return {
        "total_roles": len(postings),
        "strong_roles": decision_bands.get(_DECISION_BANDS[0], 0),
        "viable_roles": decision_bands.get(_DECISION_BANDS[0], 0)
        + decision_bands.get(_DECISION_BANDS[1], 0),
        "blocked_roles": decision_bands.get(_DECISION_BANDS[4], 0),
        "review_roles": decision_bands.get(_DECISION_BANDS[2], 0)
        + decision_bands.get(_DECISION_BANDS[3], 0),
        "role_families": _ranked(role_families),
        "work_modes": _ranked(work_modes),
        "seniority": _ranked(seniority),
        "top_companies": _ranked(companies),
        "top_locations": _ranked(locations),
        "top_skills": _ranked(skills, 20),
        "fit_distribution": [
            {"label": label, "count": decision_bands.get(label, 0)} for label in _DECISION_BANDS
        ],
        "decision_distribution": [
            {"label": label, "count": decision_bands.get(label, 0)} for label in _DECISION_BANDS
        ],
        "technical_fit_distribution": [
            {"label": label, "count": technical_fit_bands.get(label, 0)}
            for label in _TECHNICAL_FIT_BANDS
        ],
        "top_gaps": _ranked(gaps, 12),
        "study_priorities": _ranked(study_topics, 12),
        "salary_mentions": salary_mentions[:20],
        "salary_coverage": len({item["title"] + item["company"] for item in salary_mentions}),
    }


def build_market_intelligence(
    session: Session, *, timeframe: str = "all", source_scope: str = "all"
) -> dict[str, object]:
    all_postings = list(session.scalars(select(Posting).order_by(Posting.created_at.desc())).all())
    capture_statuses = _capture_statuses_by_posting(session)
    active_postings = [
        posting
        for posting in all_postings
        if not _is_archived_capture_import(capture_statuses.get(posting.id, set()))
    ]
    production_postings = [
        posting for posting in active_postings if not _is_synthetic_audit_posting(posting)
    ]
    source_filtered = _filter_by_source_scope(production_postings, capture_statuses, source_scope)
    postings = _filter_by_timeframe(source_filtered, timeframe)
    evaluations, evaluation_coverage = _effective_evaluations(session, postings)

    target_postings: list[Posting] = []
    outside_postings: list[Posting] = []
    outside_titles: Counter[str] = Counter()
    for posting in postings:
        _, is_target = _role_family(posting.title)
        if is_target:
            target_postings.append(posting)
        else:
            outside_postings.append(posting)
            outside_titles[posting.title] += 1

    return {
        "filters": {"timeframe": timeframe, "source_scope": source_scope},
        "total_unique_roles": len(postings),
        "target_role_count": len(target_postings),
        "outside_target_count": len(outside_postings),
        "target": _scope_data(target_postings, evaluations),
        "all": _scope_data(postings, evaluations),
        "evaluation_coverage": evaluation_coverage,
        "excluded_synthetic_count": len(active_postings) - len(production_postings),
        "outside_title_examples": _ranked(outside_titles, 15),
        "fit_explanation": (
            "Actionable fit combines the final recommendation with eligibility and saved preferences. "
            "Technical fit is reported separately and may remain high for a role blocked by language, relocation, shift, or another explicit requirement. "
            "Gaps and study priorities exclude blocked roles so unsuitable vacancies do not distort the development plan. "
            "The current strategy engine is preferred and the latest compatible evaluation is used as a fallback. "
            "Archived capture batches and confirmed JOLT audit fixtures are excluded from this active market view."
        ),
    }
