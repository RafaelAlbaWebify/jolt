from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select

from jolt import market_preparation_import
from jolt.ai_review_import import AIReviewImportRequest, import_ai_review
from jolt.ai_review_opportunity_index import list_ai_review_opportunity_index
from jolt.database import (
    AIReview,
    CaptureItem,
    CaptureRun,
    Posting,
    SourceDocument,
    create_session_factory,
)
from jolt.market_preparation_import import list_market_preparation_imports


def test_v2_import_persists_structured_review_and_market_insights(tmp_path, monkeypatch) -> None:
    market_path = tmp_path / "market_preparation_imports.json"
    monkeypatch.setattr(market_preparation_import, "_data_path", lambda: market_path)

    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    factory = create_session_factory(database_url)
    session = factory()
    now = datetime.now(UTC)

    try:
        source = SourceDocument(
            id="source-v2",
            source_type="linkedin",
            source_url="https://www.linkedin.com/jobs/view/200/",
            raw_text="Remote technical support. Azure preferred.",
            content_hash="c" * 64,
            captured_at=now,
        )
        capture = CaptureRun(
            id="capture-v2",
            source="linkedin",
            mode="supervised_live",
            status="completed",
            search_url="https://www.linkedin.com/jobs/search/",
            warnings_json="[]",
            requested_item_limit=1,
            observed_item_count=1,
            stop_reason="requested_limit_reached",
            started_at=now,
            completed_at=now,
        )
        session.add_all([source, capture])
        session.flush()

        posting = Posting(
            id="posting-v2",
            source_document_id=source.id,
            canonical_url=source.source_url,
            identity_key="linkedin:200",
            title="Technical Support Engineer",
            company="Example",
            location="United Kingdom · Remote",
            description="Remote technical support. Azure preferred.",
            identity_status="verified",
            created_at=now,
        )
        session.add(posting)
        session.flush()
        session.add(
            CaptureItem(
                id="item-v2",
                capture_run_id=capture.id,
                source_job_id="200",
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

        request = AIReviewImportRequest.model_validate(
            {
                "contract_type": "jolt_ai_review",
                "contract_version": "2.0",
                "capture_run_id": capture.id,
                "review_source": "chatgpt_source_first",
                "review_version": "test-v2",
                "reviewed_at": now.isoformat(),
                "jobs": [
                    {
                        "posting_id": posting.id,
                        "source_job_id": "200",
                        "decision": "pursue",
                        "priority_score": 84,
                        "geography_status": "unknown",
                        "geography_basis": "neutral_location",
                        "clearance_status": "clear",
                        "language_status": "clear",
                        "technical_fit": 82,
                        "duplicate_of_posting_id": None,
                        "hard_blockers": [],
                        "transferable_skills": ["Windows troubleshooting", "incident ownership"],
                        "skill_gaps": ["Azure administration"],
                        "learnability": "quick_1_7_days",
                        "preparation_actions": ["Complete one Azure support lab"],
                        "summary": "Good support fit; UK listing location is neutral.",
                        "reasons": ["No explicit UK-only residency restriction."],
                    }
                ],
                "market_insights": {
                    "summary": "Azure appears repeatedly in support vacancies.",
                    "demanded_technologies": ["Azure"],
                    "recurring_skill_gaps": ["Azure administration"],
                    "quick_learn_gaps": ["Azure support fundamentals"],
                    "strong_existing_skills": ["Windows support"],
                    "promising_role_families": ["Technical Support"],
                    "search_terms": ["Azure technical support"],
                    "learning_priorities": ["Continue Azure and Intune lab work"],
                    "application_strategy": ["Apply where Azure is preferred rather than mandatory"],
                },
            }
        )

        result = import_ai_review(session, request)

        assert result.received_count == 1
        assert result.created_count == 1
        assert result.market_insight_action_count == 7

        review = session.scalar(select(AIReview).where(AIReview.posting_id == posting.id))
        assert review is not None
        analysis = json.loads(review.reasons_json)
        assert analysis["geography_basis"] == "neutral_location"
        assert analysis["hard_blockers"] == []
        assert analysis["learnability"] == "quick_1_7_days"
        assert analysis["skill_gaps"] == ["Azure administration"]

        inbox = list_ai_review_opportunity_index(session)
        assert len(inbox) == 1
        assert inbox[0].geography_basis == "neutral_location"
        assert inbox[0].transferable_skills == ["Windows troubleshooting", "incident ownership"]
        assert inbox[0].learnability == "quick_1_7_days"

        market = list_market_preparation_imports()
        assert market.latest_import is not None
        assert market.latest_import.source == "chatgpt_ai_review_v2"
        assert market.latest_import.summary == "Azure appears repeatedly in support vacancies."
        assert market.latest_import.action_count == 7
    finally:
        session.close()
