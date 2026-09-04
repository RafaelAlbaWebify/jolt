from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from jolt.ai_review_import import (
    AIReviewImportRequest,
    AIReviewJob,
    import_ai_review,
)
from jolt.database import (
    AIReview,
    Application,
    CaptureItem,
    CaptureRun,
    Posting,
    SourceDocument,
    create_session_factory,
)


def _seed_capture(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    factory = create_session_factory(database_url)
    session = factory()
    now = datetime.now(UTC)

    source_1 = SourceDocument(
        id="source-ai-import-1",
        source_type="linkedin",
        source_url="https://linkedin.example/jobs/101",
        raw_text="First job source evidence.",
        content_hash="a" * 64,
        captured_at=now,
    )

    source_2 = SourceDocument(
        id="source-ai-import-2",
        source_type="linkedin",
        source_url="https://linkedin.example/jobs/102",
        raw_text="Second job source evidence.",
        content_hash="b" * 64,
        captured_at=now,
    )

    posting_1 = Posting(
        id="posting-ai-import-1",
        source_document_id=source_1.id,
        canonical_url=source_1.source_url,
        identity_key="linkedin:101",
        title="Technical Support Engineer",
        company="Example One",
        location="Spain Remote",
        description="Support role.",
        identity_status="verified",
        created_at=now,
    )

    posting_2 = Posting(
        id="posting-ai-import-2",
        source_document_id=source_2.id,
        canonical_url=source_2.source_url,
        identity_key="linkedin:102",
        title="Application Support Analyst",
        company="Example Two",
        location="Europe",
        description="Application support role.",
        identity_status="verified",
        created_at=now,
    )

    capture = CaptureRun(
        id="capture-ai-import",
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

    session.add_all([source_1, source_2, capture])
    session.flush()

    session.add_all([posting_1, posting_2])
    session.flush()

    session.add_all(
        [
            CaptureItem(
                id="item-ai-import-1",
                capture_run_id=capture.id,
                source_job_id="101",
                source_url=source_1.source_url,
                title=posting_1.title,
                company=posting_1.company,
                location=posting_1.location,
                detail_status="verified",
                verification_reasons_json="[]",
                source_document_id=source_1.id,
                posting_id=posting_1.id,
            ),
            CaptureItem(
                id="item-ai-import-2",
                capture_run_id=capture.id,
                source_job_id="102",
                source_url=source_2.source_url,
                title=posting_2.title,
                company=posting_2.company,
                location=posting_2.location,
                detail_status="verified",
                verification_reasons_json="[]",
                source_document_id=source_2.id,
                posting_id=posting_2.id,
            ),
        ]
    )

    application = Application(
        id="application-ai-import-2",
        posting_id=posting_2.id,
        status="preparing",
        application_url="https://example.test/apply",
        resume_used="resume.pdf",
        notes="Existing human workflow must survive.",
        created_at=now,
        updated_at=now,
    )

    session.add(application)
    session.commit()

    return session, capture, posting_1, posting_2, application


def _request(capture_id: str) -> AIReviewImportRequest:
    return AIReviewImportRequest(
        contract_type="jolt_ai_review",
        contract_version="1.0",
        capture_run_id=capture_id,
        review_source="chatgpt_source_first",
        review_version="2026-08-27.1",
        reviewed_at=datetime.now(UTC),
        jobs=[
            {
                "posting_id": "posting-ai-import-1",
                "source_job_id": "101",
                "decision": "strong_pursue",
                "priority_score": 94,
                "geography_status": "eligible",
                "clearance_status": "clear",
                "language_status": "clear",
                "technical_fit": 91,
                "duplicate_of_posting_id": None,
                "summary": "Strong support fit.",
                "reasons": [
                    "Spain-compatible employment.",
                    "Strong application-support alignment.",
                ],
            },
            {
                "posting_id": "posting-ai-import-2",
                "source_job_id": "102",
                "decision": "conditional",
                "priority_score": 72,
                "geography_status": "eligible",
                "clearance_status": "clear",
                "language_status": "conditional",
                "technical_fit": 84,
                "duplicate_of_posting_id": None,
                "summary": "Good fit with language condition.",
                "reasons": [
                    "Existing Application must remain untouched.",
                ],
            },
        ],
    )


def _positive_job(**overrides) -> dict:
    payload = {
        "posting_id": "posting-positive",
        "source_job_id": "positive-1",
        "decision": "pursue",
        "priority_score": 88,
        "geography_status": "eligible",
        "clearance_status": "clear",
        "language_status": "clear",
        "technical_fit": 86,
        "duplicate_of_posting_id": None,
        "summary": "Eligible and strong fit.",
        "reasons": ["Explicit compatible employment territory."],
    }
    payload.update(overrides)
    return payload


def test_positive_decision_requires_resolved_geography() -> None:
    with pytest.raises(ValueError, match="geography_status=eligible"):
        AIReviewJob.model_validate(_positive_job(geography_status="conditional"))


def test_positive_decision_requires_resolved_clearance_and_language() -> None:
    with pytest.raises(ValueError, match="clearance_status=clear"):
        AIReviewJob.model_validate(_positive_job(clearance_status="unknown"))

    with pytest.raises(ValueError, match="language_status=clear"):
        AIReviewJob.model_validate(_positive_job(language_status="conditional"))


def test_explicit_blockers_force_reject() -> None:
    with pytest.raises(ValueError, match="Ineligible geography"):
        AIReviewJob.model_validate(
            _positive_job(decision="conditional", geography_status="ineligible")
        )

    with pytest.raises(ValueError, match="Blocked language"):
        AIReviewJob.model_validate(_positive_job(decision="conditional", language_status="blocked"))


def test_duplicate_posting_cannot_be_positive_or_conditional() -> None:
    with pytest.raises(ValueError, match="Duplicate postings must use final_decision=reject"):
        AIReviewJob.model_validate(
            _positive_job(decision="conditional", duplicate_of_posting_id="canonical-posting")
        )


def test_v11_positive_decision_requires_resolved_location_eligibility() -> None:
    with pytest.raises(ValueError, match="location_eligibility=eligible"):
        AIReviewImportRequest.model_validate(
            {
                "contract_type": "jolt_ai_review",
                "contract_version": "1.1",
                "capture_run_id": "capture-1",
                "review_source": "chatgpt_source_first",
                "review_version": "eligibility-regression-1",
                "reviewed_at": datetime.now(UTC),
                "jobs": [
                    {
                        **_positive_job(),
                        "hardline_status": "PASS",
                        "hardline_reasons": [],
                        "location_eligibility": "conditional",
                        "location_evidence": [
                            "CET +/-2 only; cross-border employment not explicit"
                        ],
                        "mandatory_requirements": [],
                        "mandatory_requirement_results": [],
                        "employment_constraints": ["employment territory unresolved"],
                        "fit_analysis_allowed": True,
                        "technical_fit_percent": 86,
                        "final_decision": "pursue",
                        "decision_reason": "Good fit but territory unresolved.",
                    }
                ],
            }
        )


def test_ai_review_import_is_durable_and_preserves_application_state(
    tmp_path,
) -> None:
    session, capture, posting_1, posting_2, application = _seed_capture(tmp_path)

    try:
        result = import_ai_review(
            session,
            _request(capture.id),
        )

        assert result.received_count == 2
        assert result.created_count == 2
        assert result.updated_count == 0
        assert result.protected_human_state_count == 1

        reviews = list(session.scalars(select(AIReview).order_by(AIReview.posting_id)).all())

        assert len(reviews) == 2

        first = next(item for item in reviews if item.posting_id == posting_1.id)

        assert first.decision == "strong_pursue"
        assert first.priority_score == 94
        assert first.review_source == "chatgpt_source_first"

        retained_application = session.get(
            Application,
            application.id,
        )

        assert retained_application is not None
        assert retained_application.posting_id == posting_2.id
        assert retained_application.status == "preparing"
        assert retained_application.notes == "Existing human workflow must survive."
    finally:
        session.close()


def test_ai_review_reimport_updates_same_capture_review_without_duplicates(
    tmp_path,
) -> None:
    session, capture, *_ = _seed_capture(tmp_path)

    try:
        first_request = _request(capture.id)

        import_ai_review(
            session,
            first_request,
        )

        second_request = _request(capture.id)
        second_request.review_version = "2026-08-27.2"
        second_request.jobs[0].priority_score = 97
        second_request.jobs[0].summary = "Corrected AI review."

        result = import_ai_review(
            session,
            second_request,
        )

        assert result.created_count == 0
        assert result.updated_count == 2

        reviews = list(session.scalars(select(AIReview)).all())

        assert len(reviews) == 2

        corrected = next(item for item in reviews if item.posting_id == "posting-ai-import-1")

        assert corrected.priority_score == 97
        assert corrected.review_version == "2026-08-27.2"
        assert corrected.summary == "Corrected AI review."
    finally:
        session.close()


def test_ai_review_import_rejects_job_not_in_capture_before_writing(
    tmp_path,
) -> None:
    session, capture, *_ = _seed_capture(tmp_path)

    try:
        request = _request(capture.id)
        request.jobs[0].posting_id = "not-in-this-capture"

        with pytest.raises(
            ValueError,
            match="does not belong to the stated capture",
        ):
            import_ai_review(
                session,
                request,
            )

        assert list(session.scalars(select(AIReview)).all()) == []
    finally:
        session.close()
