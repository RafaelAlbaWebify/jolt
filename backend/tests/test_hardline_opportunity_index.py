from __future__ import annotations

import json
from datetime import UTC, datetime

from jolt.ai_review_opportunity_index import list_ai_review_opportunity_index
from jolt.database import (
    AIReview,
    CaptureItem,
    CaptureRun,
    Posting,
    SourceDocument,
    create_session_factory,
)


def test_hardline_reject_reaches_review_inbox_without_fit_score(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    factory = create_session_factory(database_url)
    now = datetime.now(UTC)

    with factory() as session:
        source = SourceDocument(
            id="source-hardline-index",
            source_type="linkedin",
            source_url="https://example.com/jobs/us-only",
            raw_text="United States · Remote. Applicants can be from anywhere in the US.",
            content_hash="e" * 64,
            captured_at=now,
        )
        capture = CaptureRun(
            id="capture-hardline-index",
            source="linkedin",
            mode="supervised_live",
            status="completed",
            search_url="https://example.com/search",
            warnings_json="[]",
            requested_item_limit=1,
            observed_item_count=1,
            stop_reason="completed",
            started_at=now,
            completed_at=now,
        )
        session.add_all([source, capture])
        session.flush()

        posting = Posting(
            id="posting-hardline-index",
            source_document_id=source.id,
            canonical_url=source.source_url,
            identity_key="linkedin:hardline-index",
            title="Technical Support Engineer L2",
            company="LucidLink",
            location="United States · Remote",
            description=source.raw_text,
            identity_status="verified",
            created_at=now,
        )
        session.add(posting)
        session.flush()
        session.add(
            CaptureItem(
                id="item-hardline-index",
                capture_run_id=capture.id,
                source_job_id="us-only",
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
        session.add(
            AIReview(
                id="review-hardline-index",
                capture_run_id=capture.id,
                posting_id=posting.id,
                source_job_id="us-only",
                review_source="chatgpt_source_first",
                review_version="hardline-v1.1",
                contract_version="1.1",
                decision="reject",
                priority_score=0,
                geography_status="ineligible",
                clearance_status="clear",
                language_status="clear",
                technical_fit=None,
                hardline_status="REJECT",
                hardline_reasons_json=json.dumps(["US-only remote requisition."]),
                location_eligibility="ineligible",
                location_evidence_json=json.dumps(
                    ["United States · Remote", "anywhere in the US"]
                ),
                mandatory_requirements_json="[]",
                mandatory_requirement_results_json="[]",
                employment_constraints_json="[]",
                fit_analysis_allowed=False,
                decision_reason="US-only remote hardline.",
                duplicate_of_posting_id=None,
                summary="Rejected at Stage 1.",
                reasons_json=json.dumps(["US-only remote requisition."]),
                reviewed_at=now,
                imported_at=now,
            )
        )
        session.commit()

        result = list_ai_review_opportunity_index(session)

        assert len(result) == 1
        item = result[0]
        assert item.decision == "reject"
        assert item.hardline_status == "REJECT"
        assert item.hardline_reasons == ["US-only remote requisition."]
        assert item.location_eligibility == "ineligible"
        assert item.fit_analysis_allowed is False
        assert item.technical_fit is None
        assert item.decision_reason == "US-only remote hardline."
