from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jolt.database import AIReview, Posting, SourceDocument, create_session_factory
from jolt.source_revalidation import (
    SourceRevalidationImportRequest,
    import_source_revalidation,
)


def _seed(tmp_path):
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")
    session = factory()
    now = datetime.now(UTC)
    source = SourceDocument(
        id="source-1",
        source_type="linkedin_live",
        source_url="https://linkedin.example/jobs/1",
        raw_text="Remote",
        content_hash="a" * 64,
        captured_at=now,
    )
    posting = Posting(
        id="posting-1",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="linkedin:1",
        title="Support",
        company="Example",
        location="Spain",
        description="Support",
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
        priority_score=91,
        geography_status="eligible",
        clearance_status="clear",
        language_status="clear",
        technical_fit=88,
        hardline_status="PASS",
        hardline_reasons_json='["existing"]',
        location_eligibility="eligible",
        location_evidence_json='["old evidence"]',
        mandatory_requirements_json='["keep me"]',
        mandatory_requirement_results_json='["keep me too"]',
        employment_constraints_json='["existing constraint"]',
        fit_analysis_allowed=True,
        decision_reason="old reason",
        summary="keep summary",
        reasons_json='["keep reason"]',
        reviewed_at=now,
        imported_at=now,
    )
    session.add(review)
    session.commit()
    return session, review


def test_hold_updates_only_source_and_location_state(tmp_path):
    session, review = _seed(tmp_path)
    request = SourceRevalidationImportRequest.model_validate(
        {
            "review_version": "source-revalidation-1",
            "items": [
                {
                    "ai_review_id": review.id,
                    "posting_id": review.posting_id,
                    "source_conflict": True,
                    "linkedin_work_model": "remote",
                    "official_work_model": "hybrid",
                    "authoritative_source": "official_ats",
                    "official_source_url": "https://example.test/official",
                    "remote_status": "not_confirmed_remote",
                    "location_verification_status": "conflict",
                    "source_confidence": "high",
                    "location_evidence": ["LinkedIn Remote", "Official Hybrid"],
                    "resolution": "hold_verify_location",
                    "reason": "Verify location.",
                }
            ],
        }
    )
    result = import_source_revalidation(session, request)
    session.refresh(review)

    assert result.updated_count == 1
    assert review.decision == "conditional"
    assert review.geography_status == "conditional"
    assert review.location_eligibility == "conditional"
    assert review.technical_fit == 88
    assert review.priority_score == 91
    assert review.mandatory_requirements_json == '["keep me"]'
    assert review.summary == "keep summary"
    assert review.source_conflict is True
    assert review.contract_version == "1.2"


def test_reject_location_clears_fit_but_preserves_other_review_evidence(tmp_path):
    session, review = _seed(tmp_path)
    request = SourceRevalidationImportRequest.model_validate(
        {
            "review_version": "source-revalidation-1",
            "items": [
                {
                    "ai_review_id": review.id,
                    "posting_id": review.posting_id,
                    "source_conflict": False,
                    "linkedin_work_model": "remote",
                    "official_work_model": "remote",
                    "authoritative_source": "official_ats",
                    "official_source_url": "https://example.test/us-only",
                    "remote_status": "confirmed_remote",
                    "location_verification_status": "verified",
                    "source_confidence": "high",
                    "location_evidence": ["Official ATS: Remote USA East Coast"],
                    "resolution": "reject_location",
                    "reason": "Official hiring territory excludes Spain.",
                }
            ],
        }
    )
    import_source_revalidation(session, request)
    session.refresh(review)

    assert review.decision == "reject"
    assert review.geography_status == "ineligible"
    assert review.location_eligibility == "ineligible"
    assert review.hardline_status == "REJECT"
    assert review.fit_analysis_allowed is False
    assert review.technical_fit is None
    assert review.priority_score == 91
    assert review.mandatory_requirements_json == '["keep me"]'


def test_preserve_remote_requires_official_remote_confirmation(tmp_path):
    session, review = _seed(tmp_path)
    request = SourceRevalidationImportRequest.model_validate(
        {
            "review_version": "source-revalidation-1",
            "items": [
                {
                    "ai_review_id": review.id,
                    "posting_id": review.posting_id,
                    "source_conflict": False,
                    "linkedin_work_model": "remote",
                    "official_work_model": "unknown",
                    "authoritative_source": "unknown",
                    "official_source_url": "",
                    "remote_status": "not_confirmed_remote",
                    "location_verification_status": "not_found",
                    "source_confidence": "low",
                    "resolution": "preserve",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="verified official remote evidence"):
        import_source_revalidation(session, request)
