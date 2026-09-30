from __future__ import annotations

from datetime import UTC, datetime

from jolt.database import AIReview, Posting, SourceDocument, create_session_factory
from jolt.hardline_revalidation import (
    HardlineRevalidationImportRequest,
    import_hardline_revalidation,
)


def _seed(tmp_path):
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")
    session = factory()
    now = datetime.now(UTC)
    source = SourceDocument(
        id="source-1",
        source_type="linkedin_live",
        source_url="https://linkedin.example/jobs/1",
        raw_text="Written English & Lithuanian required.",
        content_hash="a" * 64,
        captured_at=now,
    )
    posting = Posting(
        id="posting-1",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="linkedin:1",
        title="Technical Support",
        company="Example",
        location="Remote",
        description="Support role",
        identity_status="verified",
        created_at=now,
    )
    session.add(source)
    session.flush()
    session.add(posting)
    session.flush()
    review = AIReview(
        id="review-1",
        capture_run_id="capture-1",
        posting_id=posting.id,
        source_job_id="1",
        review_source="chatgpt_source_first",
        review_version="old",
        contract_version="1.1",
        decision="pursue",
        priority_score=84,
        geography_status="eligible",
        clearance_status="clear",
        language_status="clear",
        technical_fit=84,
        hardline_status="PASS",
        hardline_reasons_json="[]",
        location_eligibility="eligible",
        location_evidence_json="[]",
        mandatory_requirements_json='["keep"]',
        mandatory_requirement_results_json='["keep"]',
        employment_constraints_json="[]",
        fit_analysis_allowed=True,
        decision_reason="old",
        summary="keep summary",
        reasons_json='["keep reason"]',
        reviewed_at=now,
        imported_at=now,
    )
    session.add(review)
    session.commit()
    return session, review


def test_language_reject_preserves_unrelated_review_evidence(tmp_path):
    session, review = _seed(tmp_path)
    request = HardlineRevalidationImportRequest.model_validate(
        {
            "review_version": "hardline-revalidation-1",
            "items": [
                {
                    "ai_review_id": review.id,
                    "posting_id": review.posting_id,
                    "hardline_type": "language",
                    "resolution": "reject",
                    "evidence": ["Written English & Lithuanian required."],
                    "reason": "Mandatory Lithuanian is not satisfied.",
                }
            ],
        }
    )
    result = import_hardline_revalidation(session, request)
    session.refresh(review)

    assert result.updated_count == 1
    assert review.decision == "reject"
    assert review.hardline_status == "REJECT"
    assert review.language_status == "blocked"
    assert review.fit_analysis_allowed is False
    assert review.technical_fit is None
    assert review.priority_score == 84
    assert review.summary == "keep summary"
    assert review.mandatory_requirements_json == '["keep"]'


def test_hardline_hold_sets_manual_review(tmp_path):
    session, review = _seed(tmp_path)
    request = HardlineRevalidationImportRequest.model_validate(
        {
            "review_version": "hardline-revalidation-1",
            "items": [
                {
                    "ai_review_id": review.id,
                    "posting_id": review.posting_id,
                    "hardline_type": "certification",
                    "resolution": "hold",
                    "evidence": ["Certification required."],
                    "reason": "Certification status needs verification.",
                }
            ],
        }
    )
    import_hardline_revalidation(session, request)
    session.refresh(review)

    assert review.decision == "conditional"
    assert review.hardline_status == "MANUAL_REVIEW"
    assert review.clearance_status == "conditional"
    assert review.fit_analysis_allowed is False
    assert review.technical_fit is None
