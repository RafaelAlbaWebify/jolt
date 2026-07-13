from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from jolt.database import Base, Posting, utc_now

READINESS_ENGINE_VERSION = "application-readiness-v1"
PROFILE_VERSION_ID = "rafael-job-search:v2"


class ApplicationReadiness(Base):
    __tablename__ = "application_readiness_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    posting_id: Mapped[str] = mapped_column(ForeignKey("postings.id"), index=True)
    profile_version_id: Mapped[str] = mapped_column(String(80), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    readiness_score: Mapped[int] = mapped_column(nullable=False)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class ReadinessAnalysis:
    priority: str
    readiness_score: int
    evidence_matches: list[str]
    credibility_warnings: list[str]
    cv_tailoring_points: list[str]
    talking_points: list[str]
    interview_questions: list[str]
    revision_topics: list[str]
    checklist: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "priority": self.priority,
            "readiness_score": self.readiness_score,
            "evidence_matches": self.evidence_matches,
            "credibility_warnings": self.credibility_warnings,
            "cv_tailoring_points": self.cv_tailoring_points,
            "talking_points": self.talking_points,
            "interview_questions": self.interview_questions,
            "revision_topics": self.revision_topics,
            "checklist": self.checklist,
        }


EVIDENCE_LIBRARY: dict[str, tuple[list[str], str, str]] = {
    "incident_ownership": (
        ["incident", "troubleshoot", "root cause", "escalation", "production support"],
        (
            "Production-critical IT support with incident ownership, evidence collection, "
            "escalation, and runbook documentation."
        ),
        (
            "Emphasize ownership from symptom reproduction through evidence-backed escalation "
            "and validation."
        ),
    ),
    "application_support": (
        ["application support", "software support", "logs", "api", "integration", "sql"],
        (
            "Support-side experience with SQL-dependent manufacturing applications, logs, "
            "integrations, and controlled validation."
        ),
        (
            "Position SQL, logs, and integrations as troubleshooting tools rather than claiming "
            "developer or DBA ownership."
        ),
    ),
    "infrastructure": (
        ["microsoft 365", "entra", "azure ad", "windows", "dns", "network", "vmware", "backup"],
        (
            "Hands-on Windows, Microsoft 365, Entra ID, DNS, networking, VMware, and backup "
            "operations experience."
        ),
        "Lead with the infrastructure technologies explicitly requested by the posting.",
    ),
    "manufacturing_operations": (
        ["manufacturing", "mes", "plant", "production environment", "24/7"],
        (
            "Manufacturing IT exposure supporting production-critical MES and plant systems "
            "under operational pressure."
        ),
        (
            "Use manufacturing examples only when the role values production continuity, "
            "operations, or industrial environments."
        ),
    ),
    "automation_documentation": (
        ["powershell", "automation", "python", "scripting", "runbook", "documentation"],
        (
            "PowerShell/Python automation awareness plus substantial operational documentation "
            "and runbook practice."
        ),
        (
            "Describe automation as safe operational tooling with evidence and repeatability, "
            "not autonomous system modification."
        ),
    ),
}

UNSUPPORTED_CLAIMS: dict[str, list[str]] = {
    "software_development": [
        "software developer",
        "full stack",
        "frontend developer",
        "backend developer",
    ],
    "formal_management": ["people manager", "direct reports", "performance reviews", "head of"],
    "advanced_database_ownership": ["database administrator", "dba", "database architect"],
}


def _contains(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def analyze_readiness(posting: Posting) -> ReadinessAnalysis:
    text = "\n".join([posting.title, posting.location, posting.description]).lower()
    evidence_matches: list[str] = []
    cv_points: list[str] = []
    revision_topics: list[str] = []

    for terms, evidence, tailoring in EVIDENCE_LIBRARY.values():
        if _contains(text, terms):
            evidence_matches.append(evidence)
            cv_points.append(tailoring)

    warnings: list[str] = []
    if _contains(text, UNSUPPORTED_CLAIMS["software_development"]):
        warnings.append(
            "Do not present Rafael as a software developer; clarify support and troubleshooting scope."
        )
    if _contains(text, UNSUPPORTED_CLAIMS["formal_management"]):
        warnings.append("Formal people-management evidence is not established.")
    if _contains(text, UNSUPPORTED_CLAIMS["advanced_database_ownership"]):
        warnings.append(
            "Do not claim DBA ownership; describe SQL-dependent application support accurately."
        )
    if "german" in text or "french" in text:
        warnings.append(
            "Confirm whether the additional language is mandatory; Rafael can claim English and Spanish only."
        )

    if _contains(text, ["sql", "database"]):
        revision_topics.append(
            "SQL support queries, joins, filtering, safe read-only diagnostics, and escalation boundaries."
        )
    if _contains(text, ["api", "integration", "rest"]):
        revision_topics.append(
            "HTTP status codes, REST requests, authentication concepts, payload validation, and integration evidence."
        )
    if _contains(text, ["logs", "monitoring", "production support"]):
        revision_topics.append(
            "Log correlation, timestamps, severity, reproduction, evidence packaging, and RCA structure."
        )
    if _contains(text, ["dns", "network", "tcp", "firewall"]):
        revision_topics.append(
            "DNS resolution, ports, TCP reachability, firewall evidence, and layered troubleshooting."
        )
    if _contains(text, ["cloud", "aws", "azure"]):
        revision_topics.append(
            "Cloud shared responsibility, service health, IAM basics, availability, and support escalation."
        )

    interview_questions = [
        "Describe a production-critical incident you owned from first symptom to validated resolution or escalation.",
        "How do you distinguish an application problem from a network, DNS, database, or endpoint problem?",
        "What evidence do you collect before escalating a software or integration issue?",
    ]
    if "sql" in text:
        interview_questions.append(
            "How have you used SQL safely while supporting an application without acting as the DBA?"
        )
    if "api" in text or "integration" in text:
        interview_questions.append(
            "How would you troubleshoot an API or system-integration failure end to end?"
        )

    score = min(
        100,
        35 + len(evidence_matches) * 12 + len(revision_topics) * 3 - len(warnings) * 8,
    )
    if len(evidence_matches) >= 4 and not warnings:
        priority = "high"
    elif len(evidence_matches) >= 2:
        priority = "medium"
    else:
        priority = "low"

    checklist = [
        (
            "Confirm location, remote eligibility from Spain, contract type, salary, shifts, "
            "on-call, and travel."
        ),
        "Open the source posting and verify that the captured description is complete and current.",
        "Select only evidence-backed CV points; do not add unsupported tools, duties, or seniority.",
        "Prepare one incident-ownership example and one technical troubleshooting example.",
        "Record the exact CV version and application URL before submission.",
    ]

    return ReadinessAnalysis(
        priority=priority,
        readiness_score=max(0, score),
        evidence_matches=evidence_matches,
        credibility_warnings=warnings,
        cv_tailoring_points=cv_points,
        talking_points=evidence_matches[:3],
        interview_questions=interview_questions,
        revision_topics=revision_topics,
        checklist=checklist,
    )


def ensure_readiness_report(session: Session, posting: Posting) -> ApplicationReadiness:
    existing = session.scalar(
        select(ApplicationReadiness)
        .where(
            ApplicationReadiness.posting_id == posting.id,
            ApplicationReadiness.engine_version == READINESS_ENGINE_VERSION,
            ApplicationReadiness.profile_version_id == PROFILE_VERSION_ID,
        )
        .order_by(ApplicationReadiness.created_at.desc())
    )
    if existing is not None:
        return existing

    analysis = analyze_readiness(posting)
    report = ApplicationReadiness(
        id=str(uuid4()),
        posting_id=posting.id,
        profile_version_id=PROFILE_VERSION_ID,
        engine_version=READINESS_ENGINE_VERSION,
        priority=analysis.priority,
        readiness_score=analysis.readiness_score,
        report_json=json.dumps(analysis.as_dict(), sort_keys=True),
        created_at=utc_now(),
    )
    session.add(report)
    session.commit()
    return report


def readiness_payload(report: ApplicationReadiness) -> dict[str, object]:
    payload = json.loads(report.report_json)
    payload.update(
        {
            "report_id": report.id,
            "profile_version_id": report.profile_version_id,
            "engine_version": report.engine_version,
        }
    )
    return payload
