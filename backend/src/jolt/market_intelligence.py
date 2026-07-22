from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Evaluation, Posting
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
            "product support",
            "software support",
            "solutions support",
            "customer technical",
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
    if any(term in value for term in (" junior ", " jr ", " entry ")):
        return "Junior"
    return "Mid / unspecified"


def _salary_mentions(text: str) -> list[str]:
    patterns = (
        r"(?:€|eur\s*)\s?\d{2,3}(?:[.,]\d{3})?(?:\s?[-–]\s?(?:€|eur\s*)?\s?\d{2,3}(?:[.,]\d{3})?)?",
        r"\d{2,3}(?:[.,]\d{3})?\s?(?:€|eur)(?:\s?[-–]\s?\d{2,3}(?:[.,]\d{3})?\s?(?:€|eur))?",
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


def _fit_band(score: int) -> str:
    if score >= 80:
        return "Strong match · 80–100"
    if score >= 60:
        return "Viable with preparation · 60–79"
    if score >= 40:
        return "Stretch · 40–59"
    return "Low priority · 0–39"


def _ranked(counter: Counter[str], limit: int = 12) -> list[dict[str, object]]:
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def _scope_data(postings: list[Posting], evaluations: dict[str, Evaluation]) -> dict[str, object]:
    role_families: Counter[str] = Counter()
    work_modes: Counter[str] = Counter()
    seniority: Counter[str] = Counter()
    companies: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    score_bands: Counter[str] = Counter()
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
            score_bands[_fit_band(evaluation.ranking_score)] += 1
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

    ordered_bands = (
        "Strong match · 80–100",
        "Viable with preparation · 60–79",
        "Stretch · 40–59",
        "Low priority · 0–39",
    )
    return {
        "total_roles": len(postings),
        "strong_roles": score_bands.get(ordered_bands[0], 0),
        "viable_roles": score_bands.get(ordered_bands[0], 0) + score_bands.get(ordered_bands[1], 0),
        "role_families": _ranked(role_families),
        "work_modes": _ranked(work_modes),
        "seniority": _ranked(seniority),
        "top_companies": _ranked(companies),
        "top_locations": _ranked(locations),
        "top_skills": _ranked(skills, 20),
        "fit_distribution": [
            {"label": label, "count": score_bands.get(label, 0)} for label in ordered_bands
        ],
        "top_gaps": _ranked(gaps, 12),
        "study_priorities": _ranked(study_topics, 12),
        "salary_mentions": salary_mentions[:20],
        "salary_coverage": len({item["title"] + item["company"] for item in salary_mentions}),
    }


def build_market_intelligence(session: Session) -> dict[str, object]:
    postings = list(session.scalars(select(Posting).order_by(Posting.created_at.desc())).all())
    evaluations = list(
        session.scalars(
            select(Evaluation)
            .where(Evaluation.engine_version == ENGINE_VERSION)
            .order_by(Evaluation.created_at.desc())
        ).all()
    )
    latest_evaluations: dict[str, Evaluation] = {}
    for evaluation in evaluations:
        latest_evaluations.setdefault(evaluation.posting_id, evaluation)

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
        "total_unique_roles": len(postings),
        "target_role_count": len(target_postings),
        "outside_target_count": len(outside_postings),
        "target": _scope_data(target_postings, latest_evaluations),
        "all": _scope_data(postings, latest_evaluations),
        "outside_title_examples": _ranked(outside_titles, 15),
        "fit_explanation": (
            "Fit scores measure alignment with the active target profile, not general "
            "employability. Outside-target captures should be used to improve search filters, "
            "not to judge career fit."
        ),
    }
