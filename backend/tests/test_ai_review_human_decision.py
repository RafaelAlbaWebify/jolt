from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from jolt.database import (
    AIReview,
    Application,
    CaptureRun,
    Posting,
    ReviewDecision,
    SourceDocument,
    create_session_factory,
)
from jolt.schemas import ReviewRequest
from jolt.workflow import record_review


def _seed(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"

    factory = create_session_factory(database_url)
    session = factory()
    now = datetime.now(UTC)

    source = SourceDocument(
        id="source-ai-human",
        source_type="linkedin",
        source_url="https://linkedin.example/jobs/501",
        raw_text="Application support role.",
        content_hash="e" * 64,
        captured_at=now,
    )

    posting = Posting(
        id="posting-ai-human",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="linkedin:501",
        title="Application Support Analyst",
        company="Example",
        location="Spain Remote",
        description="Application support role.",
        identity_status="verified",
        created_at=now,
    )

    capture = CaptureRun(
        id="capture-ai-human",
        source="linkedin",
        mode="supervised_live",
        status="completed",
        search_url="https://linkedin.example/search",
        warnings_json="[]",
        requested_item_limit=1,
        observed_item_count=1,
        stop_reason="no_next_page",
        started_at=now,
        completed_at=now,
    )

    session.add_all([source, capture])
    session.flush()

    session.add(posting)
    session.flush()

    ai_review = AIReview(
        id="ai-review-human",
        capture_run_id=capture.id,
        posting_id=posting.id,
        source_job_id="501",
        review_source="chatgpt_source_first",
        review_version="2026-08-27.1",
        contract_version="1.0",
        decision="strong_pursue",
        priority_score=94,
        geography_status="eligible",
        clearance_status="clear",
        language_status="clear",
        technical_fit=91,
        duplicate_of_posting_id=None,
        summary="Strong fit.",
        reasons_json='["Spain eligible."]',
        reviewed_at=now,
        imported_at=now,
    )

    session.add(ai_review)
    session.commit()

    return session, posting, ai_review


def test_pursue_from_ai_review_creates_application_without_evaluation(
    tmp_path,
) -> None:
    session, posting, ai_review = _seed(tmp_path)

    try:
        response = record_review(
            session,
            posting.id,
            ReviewRequest(
                ai_review_id=ai_review.id,
                decision="pursue",
            ),
        )

        assert response.evaluation_id is None
        assert response.ai_review_id == ai_review.id

        saved_review = session.scalar(
            select(ReviewDecision).where(ReviewDecision.posting_id == posting.id)
        )

        assert saved_review is not None
        assert saved_review.evaluation_id is None
        assert saved_review.ai_review_id == ai_review.id

        application = session.scalar(
            select(Application).where(Application.posting_id == posting.id)
        )

        assert application is not None
        assert application.status == "preparing"
    finally:
        session.close()


def test_reject_from_ai_review_does_not_create_application(
    tmp_path,
) -> None:
    session, posting, ai_review = _seed(tmp_path)

    try:
        response = record_review(
            session,
            posting.id,
            ReviewRequest(
                ai_review_id=ai_review.id,
                decision="reject",
            ),
        )

        assert response.ai_review_id == ai_review.id
        assert response.evaluation_id is None

        application = session.scalar(
            select(Application).where(Application.posting_id == posting.id)
        )

        assert application is None
    finally:
        session.close()
