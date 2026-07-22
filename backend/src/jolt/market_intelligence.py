from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Evaluation, Posting

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


def _role_family(title: str) -> str:
    value = title.lower()
    if "application" in value and "support" in value:
        return "Application support"
    if "production" in value and "support" in value:
        return "Production support"
    if "technical" in value and "support" in value:
        return "Technical support"
    if "service" in value and ("manager" in value or "management" in value):
        return "Service management"
    if "customer" in value and "support" in value:
        return "Customer support"
    if "support" in value:
        return "General IT support"
    if "qa" in value or "quality assurance" in value:
        return "Quality assurance"
    return "Other"


def _work_mode(location: str, description: str) -> str:
    value = f"{location} {description}".lower()
    if "hybrid" in value or "híbrido" in value:
        return "Hybrid"
    if "remote" in value or "remoto" in value:
        return "Remote"
    return "Onsite / unspecified"


def _seniority(title: str) -> str:
    value = title.lower()
    if any(term in value for term in ("lead", "principal", "manager", "head")):
        return "Lead / management"
    if any(term in value for term in ("senior", "sr.", "sr ", "level 3", "l3")):
        return "Senior"
    if any(term in value for term in ("junior", "jr.", "jr ", "entry")):
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


def build_market_intelligence(session: Session) -> dict[str, object]:
    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()
    evaluations = session.scalars(select(Evaluation).order_by(Evaluation.created_at.desc())).all()
    latest_evaluations: dict[str, Evaluation] = {}
    for evaluation in evaluations:
        latest_evaluations.setdefault(evaluation.posting_id, evaluation)

    role_families: Counter[str] = Counter()
    work_modes: Counter[str] = Counter()
    seniority: Counter[str] = Counter()
    companies: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    score_bands: Counter[str] = Counter()
    salary_mentions: list[dict[str, str]] = []

    for posting in postings:
        role_families[_role_family(posting.title)] += 1
        work_modes[_work_mode(posting.location, posting.description)] += 1
        seniority[_seniority(posting.title)] += 1
        if posting.company:
            companies[posting.company] += 1
        if posting.location:
            locations[posting.location] += 1

        searchable = f"{posting.title}\n{posting.description}".lower()
        for skill in SKILL_TERMS:
            if skill in searchable:
                skills[
                    skill.upper()
                    if skill in {"sql", "aws", "dns", "dhcp", "api"}
                    else skill.title()
                ] += 1

        evaluation = latest_evaluations.get(posting.id)
        if evaluation:
            score = evaluation.ranking_score
            band = (
                "80–100"
                if score >= 80
                else "60–79"
                if score >= 60
                else "40–59"
                if score >= 40
                else "0–39"
            )
            score_bands[band] += 1

        for mention in _salary_mentions(posting.description):
            salary_mentions.append(
                {"title": posting.title, "company": posting.company, "mention": mention}
            )

    def ranked(counter: Counter[str], limit: int = 12) -> list[dict[str, object]]:
        return [{"label": label, "count": count} for label, count in counter.most_common(limit)]

    return {
        "total_unique_roles": len(postings),
        "role_families": ranked(role_families),
        "work_modes": ranked(work_modes),
        "seniority": ranked(seniority),
        "top_companies": ranked(companies),
        "top_locations": ranked(locations),
        "top_skills": ranked(skills, 20),
        "fit_distribution": [
            {"label": label, "count": score_bands.get(label, 0)}
            for label in ("80–100", "60–79", "40–59", "0–39")
        ],
        "salary_mentions": salary_mentions[:20],
        "salary_coverage": len({item["title"] + item["company"] for item in salary_mentions}),
    }
