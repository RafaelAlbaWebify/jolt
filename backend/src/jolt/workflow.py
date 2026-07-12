from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Evaluation, Posting, ProfileVersion, ReviewDecision, SourceDocument, utc_now
from jolt.schemas import IntakeResponse, ManualIntakeRequest, OpportunitySummary, ReviewRequest, ReviewResponse

PROFILE_ID = "default-job-search"
PROFILE_VERSION_ID = "default-job-search:v1"
ENGINE_VERSION = "rules-v1"

PROFILE_CONFIGURATION = {
    "positive_terms": [
        "application support",
        "production support",
        "technical support",
        "sql",
        "incident",
        "infrastructure",
        "automation",
        "api",
        "integration",
    ],
    "hard_reject_phrases": [
        "mandatory german",
        "german is mandatory",
        "must speak german",
        "mandatory french",
        "french is mandatory",
        "must speak french",
    ],
}


@dataclass(frozen=True)
class ParsedPosting:
    title: str
    company: str
    location: str
    description: str


def normalize_url(value: str) -> str:
    if not value.strip():
        return ""
    parts = urlsplit(value.strip())
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"trk", "ref", "refid"}
    ]
    return urlunsplit(parts._replace(query=urlencode(query), fragment="")).rstrip("/")


def parse_manual_text(raw_text: str) -> ParsedPosting:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    title = lines[0] if lines else ""
    company = lines[1] if len(lines) > 1 else ""
    location = ""
    for line in lines:
        match = re.match(r"(?i)^location\s*:\s*(.+)$", line)
        if match:
            location = match.group(1).strip()
            break
    return ParsedPosting(title=title, company=company, location=location, description=raw_text.strip())


def ensure_default_profile(session: Session) -> ProfileVersion:
    profile = session.get(ProfileVersion, PROFILE_VERSION_ID)
    if profile is not None:
        return profile
    profile = ProfileVersion(
        id=PROFILE_VERSION_ID,
        profile_id=PROFILE_ID,
        version=1,
        configuration_json=json.dumps(PROFILE_CONFIGURATION, sort_keys=True),
        created_at=utc_now(),
    )
    session.add(profile)
    session.flush()
    return profile


def evaluate_text(text: str) -> tuple[str, str, int, list[str]]:
    lowered = text.lower()
    blockers = [phrase for phrase in PROFILE_CONFIGURATION["hard_reject_phrases"] if phrase in lowered]
    matches = [term for term in PROFILE_CONFIGURATION["positive_terms"] if term in lowered]
    reasons: list[str] = []

    if blockers:
        reasons.append(f"Verified blocking phrase(s): {', '.join(blockers)}.")
        return "reject", "high", 0, reasons

    if matches:
        reasons.append(f"Relevant signal(s): {', '.join(matches)}.")
    score = min(100, 35 + len(matches) * 12)
    if len(matches) >= 3:
        return "pursue", "medium", score, reasons
    reasons.append("No verified hard blocker; more evidence or human review may be needed.")
    return "consider", "medium" if matches else "low", score, reasons


def ingest_manual(session: Session, request: ManualIntakeRequest) -> IntakeResponse:
    content_hash = hashlib.sha256(request.raw_text.encode("utf-8")).hexdigest()
    source = SourceDocument(
        id=str(uuid4()),
        source_type=request.source_type,
        source_url=request.source_url,
        raw_text=request.raw_text,
        content_hash=content_hash,
        captured_at=utc_now(),
    )
    session.add(source)
    session.flush()

    canonical_url = normalize_url(request.source_url)
    duplicate_query = select(Posting).join(SourceDocument).where(SourceDocument.content_hash == content_hash)
    if canonical_url:
        duplicate_query = select(Posting).where(Posting.canonical_url == canonical_url)
    duplicate = session.scalar(duplicate_query)
    if duplicate is not None:
        evaluation = session.scalar(
            select(Evaluation).where(Evaluation.posting_id == duplicate.id).order_by(Evaluation.created_at.desc())
        )
        if evaluation is None:
            raise RuntimeError("Duplicate posting exists without an evaluation.")
        session.commit()
        return IntakeResponse(
            source_document_id=source.id,
            posting_id=duplicate.id,
            evaluation_id=evaluation.id,
            identity_status="confirmed_duplicate",
            duplicate_of_posting_id=duplicate.id,
            title=duplicate.title,
            company=duplicate.company,
            location=duplicate.location,
            recommendation=evaluation.recommendation,  # type: ignore[arg-type]
            confidence=evaluation.confidence,
            ranking_score=evaluation.ranking_score,
            reasons=json.loads(evaluation.reasons_json),
            profile_version_id=evaluation.profile_version_id,
            engine_version=evaluation.engine_version,
        )

    parsed = parse_manual_text(request.raw_text)
    posting = Posting(
        id=str(uuid4()),
        source_document_id=source.id,
        canonical_url=canonical_url,
        title=parsed.title,
        company=parsed.company,
        location=parsed.location,
        description=parsed.description,
        identity_status="new",
        created_at=utc_now(),
    )
    session.add(posting)
    profile = ensure_default_profile(session)
    recommendation, confidence, score, reasons = evaluate_text(parsed.description)
    evaluation = Evaluation(
        id=str(uuid4()),
        posting_id=posting.id,
        profile_version_id=profile.id,
        engine_version=ENGINE_VERSION,
        recommendation=recommendation,
        confidence=confidence,
        ranking_score=score,
        reasons_json=json.dumps(reasons),
        created_at=utc_now(),
    )
    session.add(evaluation)
    session.commit()

    return IntakeResponse(
        source_document_id=source.id,
        posting_id=posting.id,
        evaluation_id=evaluation.id,
        identity_status="new",
        title=posting.title,
        company=posting.company,
        location=posting.location,
        recommendation=recommendation,  # type: ignore[arg-type]
        confidence=confidence,
        ranking_score=score,
        reasons=reasons,
        profile_version_id=profile.id,
        engine_version=ENGINE_VERSION,
    )


def record_review(session: Session, posting_id: str, request: ReviewRequest) -> ReviewResponse:
    posting = session.get(Posting, posting_id)
    evaluation = session.get(Evaluation, request.evaluation_id)
    if posting is None or evaluation is None or evaluation.posting_id != posting_id:
        raise LookupError("Posting or evaluation was not found.")
    review = ReviewDecision(
        id=str(uuid4()),
        posting_id=posting_id,
        evaluation_id=evaluation.id,
        decision=request.decision,
        reason_code=request.reason_code,
        notes=request.notes,
        evaluation_overridden=request.decision != evaluation.recommendation,
        reviewed_at=utc_now(),
    )
    session.add(review)
    session.commit()
    return ReviewResponse(
        review_id=review.id,
        posting_id=posting_id,
        evaluation_id=evaluation.id,
        decision=request.decision,
        evaluation_overridden=review.evaluation_overridden,
    )


def list_opportunities(session: Session) -> list[OpportunitySummary]:
    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()
    results: list[OpportunitySummary] = []
    for posting in postings:
        evaluation = session.scalar(
            select(Evaluation).where(Evaluation.posting_id == posting.id).order_by(Evaluation.created_at.desc())
        )
        if evaluation is None:
            continue
        review = session.scalar(
            select(ReviewDecision)
            .where(ReviewDecision.posting_id == posting.id)
            .order_by(ReviewDecision.reviewed_at.desc())
        )
        results.append(
            OpportunitySummary(
                posting_id=posting.id,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                recommendation=evaluation.recommendation,  # type: ignore[arg-type]
                ranking_score=evaluation.ranking_score,
                review_decision=review.decision if review else None,  # type: ignore[arg-type]
            )
        )
    return results
