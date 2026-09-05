from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from jolt.ai_review_import import AIReviewImportRequest, import_ai_review
from jolt.database import (
    AIReview,
    CaptureItem,
    CaptureRun,
    Posting,
    SourceDocument,
    create_session_factory,
)


def _seed_two_job_capture(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    factory = create_session_factory(database_url)
    session = factory()
    now = datetime.now(UTC)

    capture = CaptureRun(
        id="capture-exact-review",
        source="linkedin",
        mode="supervised_live",
        status="completed",
        search_url="https://linkedin.example/search",
        warnings_json="[]",
        requested_item_limit=2,
        observed_item_count=2,
        stop_reason="no_next_page",
        started_at=now,
        completed_at=now,
    )
    session.add(capture)

    for suffix in ("1", "2"):
        source = SourceDocument(
            id=f"source-exact-{suffix}",
            source_type="linkedin",
            source_url=f"https://linkedin.example/jobs/{suffix}",
            raw_text=f"Support role {suffix} in Spain.",
            content_hash=suffix * 64,
            captured_at=now,
        )
        posting = Posting(
            id=f"posting-exact-{suffix}",
            source_document_id=source.id,
            canonical_url=source.source_url,
            identity_key=f"linkedin:exact:{suffix}",
            title=f"Support Engineer {suffix}",
            company="Example",
            location="Spain Remote",
            description=f"Support role {suffix}.",
            identity_status="verified",
            created_at=now,
        )
        session.add(source)
        session.flush()
        session.add(posting)
        session.flush()
        session.add(
            CaptureItem(
                id=f"item-exact-{suffix}",
                capture_run_id=capture.id,
                source_job_id=suffix,
                source_url=source.source_url,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                detail_status="verified",
                verification_reasons_json="[]",
                source_document_id=source.id,
                posting_id=posting.id,
            )
        )

    session.commit()
    return session, capture


def _v11_job(posting_id: str, source_job_id: str) -> dict:
    return {
        "posting_id": posting_id,
        "source_job_id": source_job_id,
        "hardline_status": "PASS",
        "hardline_reasons": [],
        "location_eligibility": "eligible",
        "location_evidence": ["Spain Remote"],
        "mandatory_requirements": [],
        "mandatory_requirement_results": [],
        "employment_constraints": [],
        "fit_analysis_allowed": True,
        "technical_fit_percent": 80,
        "final_decision": "pursue",
        "decision_reason": "Eligible support role.",
        "decision": "pursue",
        "priority_score": 80,
        "geography_status": "eligible",
        "clearance_status": "clear",
        "language_status": "clear",
        "technical_fit": 80,
        "duplicate_of_posting_id": None,
        "summary": "Eligible support role.",
        "reasons": ["Spain-compatible role."],
    }


def test_v11_import_rejects_omitted_capture_posting_before_writing(tmp_path) -> None:
    session, capture = _seed_two_job_capture(tmp_path)
    try:
        request = AIReviewImportRequest.model_validate(
            {
                "contract_type": "jolt_ai_review",
                "contract_version": "1.1",
                "capture_run_id": capture.id,
                "review_source": "chatgpt_source_first",
                "review_version": "exact-completeness-regression-1",
                "reviewed_at": datetime.now(UTC),
                "jobs": [_v11_job("posting-exact-1", "1")],
            }
        )

        with pytest.raises(
            ValueError,
            match="must return exactly one result for every posting in the capture",
        ):
            import_ai_review(session, request)

        assert list(session.scalars(select(AIReview)).all()) == []
    finally:
        session.close()


def test_v11_import_accepts_exact_capture_posting_set(tmp_path) -> None:
    session, capture = _seed_two_job_capture(tmp_path)
    try:
        request = AIReviewImportRequest.model_validate(
            {
                "contract_type": "jolt_ai_review",
                "contract_version": "1.1",
                "capture_run_id": capture.id,
                "review_source": "chatgpt_source_first",
                "review_version": "exact-completeness-regression-1",
                "reviewed_at": datetime.now(UTC),
                "jobs": [
                    _v11_job("posting-exact-1", "1"),
                    _v11_job("posting-exact-2", "2"),
                ],
            }
        )

        result = import_ai_review(session, request)

        assert result.received_count == 2
        assert result.created_count == 2
        assert len(list(session.scalars(select(AIReview)).all())) == 2
    finally:
        session.close()
