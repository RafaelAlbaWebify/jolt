from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Evaluation, Posting, SourceDocument, utc_now
from jolt.schemas import IntakeResponse, ManualIntakeRequest
from jolt.workflow import (
    ENGINE_VERSION,
    ensure_default_profile,
    evaluate_text,
    normalize_url,
    parse_manual_text,
)


def ingest_capture_item(session: Session, request: ManualIntakeRequest) -> IntakeResponse:
    """Stage one captured posting without committing the surrounding capture transaction."""
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
    duplicate_query = (
        select(Posting).join(SourceDocument).where(SourceDocument.content_hash == content_hash)
    )
    if canonical_url:
        duplicate_query = select(Posting).where(Posting.canonical_url == canonical_url)
    duplicate = session.scalar(duplicate_query)

    if duplicate is not None:
        evaluation = session.scalar(
            select(Evaluation)
            .where(Evaluation.posting_id == duplicate.id)
            .order_by(Evaluation.created_at.desc())
        )
        if evaluation is None:
            raise RuntimeError("Duplicate posting exists without an evaluation.")
        return IntakeResponse(
            source_document_id=source.id,
            posting_id=duplicate.id,
            evaluation_id=evaluation.id,
            identity_status="confirmed_duplicate",
            duplicate_of_posting_id=duplicate.id,
            title=duplicate.title,
            company=duplicate.company,
            location=duplicate.location,
            recommendation=evaluation.recommendation,
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
    session.flush()

    return IntakeResponse(
        source_document_id=source.id,
        posting_id=posting.id,
        evaluation_id=evaluation.id,
        identity_status="new",
        title=posting.title,
        company=posting.company,
        location=posting.location,
        recommendation=recommendation,
        confidence=confidence,
        ranking_score=score,
        reasons=reasons,
        profile_version_id=profile.id,
        engine_version=ENGINE_VERSION,
    )
