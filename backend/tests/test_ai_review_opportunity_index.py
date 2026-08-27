from __future__ import annotations

import json
from datetime import UTC, datetime

from jolt.ai_review_opportunity_index import (
    list_ai_review_opportunity_index,
)
from jolt.database import (
    AIReview,
    CaptureItem,
    CaptureRun,
    Evaluation,
    Posting,
    ProfileVersion,
    SourceDocument,
    create_session_factory,
)


def test_ai_review_index_ignores_python_classifier_scores(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"

    factory = create_session_factory(database_url)
    session = factory()
    now = datetime.now(UTC)

    try:
        source_a = SourceDocument(
            id="source-ai-index-a",
            source_type="linkedin",
            source_url="https://linkedin.example/jobs/a",
            raw_text="Job A",
            content_hash="a" * 64,
            captured_at=now,
        )

        source_b = SourceDocument(
            id="source-ai-index-b",
            source_type="linkedin",
            source_url="https://linkedin.example/jobs/b",
            raw_text="Job B",
            content_hash="b" * 64,
            captured_at=now,
        )

        posting_a = Posting(
            id="posting-ai-index-a",
            source_document_id=source_a.id,
            canonical_url=source_a.source_url,
            identity_key="linkedin:index-a",
            title="Application Support Analyst",
            company="Example A",
            location="Spain Remote",
            description="Application support.",
            identity_status="verified",
            created_at=now,
        )

        posting_b = Posting(
            id="posting-ai-index-b",
            source_document_id=source_b.id,
            canonical_url=source_b.source_url,
            identity_key="linkedin:index-b",
            title="Support Engineer",
            company="Example B",
            location="Remote",
            description="Support engineer.",
            identity_status="verified",
            created_at=now,
        )

        capture = CaptureRun(
            id="capture-ai-index",
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

        profile = ProfileVersion(
            id="profile-ai-index",
            profile_id="legacy-python",
            version=1,
            configuration_json="{}",
            created_at=now,
        )

        session.add_all(
            [
                source_a,
                source_b,
                capture,
                profile,
            ]
        )
        session.flush()

        session.add_all(
            [
                posting_a,
                posting_b,
            ]
        )
        session.flush()

        session.add_all(
            [
                CaptureItem(
                    id="item-ai-index-a",
                    capture_run_id=capture.id,
                    source_job_id="a",
                    source_url=source_a.source_url,
                    title=posting_a.title,
                    company=posting_a.company,
                    location=posting_a.location,
                    detail_status="verified",
                    verification_reasons_json="[]",
                    source_document_id=source_a.id,
                    posting_id=posting_a.id,
                ),
                CaptureItem(
                    id="item-ai-index-b",
                    capture_run_id=capture.id,
                    source_job_id="b",
                    source_url=source_b.source_url,
                    title=posting_b.title,
                    company=posting_b.company,
                    location=posting_b.location,
                    detail_status="verified",
                    verification_reasons_json="[]",
                    source_document_id=source_b.id,
                    posting_id=posting_b.id,
                ),
            ]
        )

        # Deliberately wrong legacy Python classification.
        session.add(
            Evaluation(
                id="legacy-evaluation-a",
                posting_id=posting_a.id,
                profile_version_id=profile.id,
                engine_version="legacy-python",
                recommendation="do_not_pursue",
                confidence="high",
                ranking_score=0,
                reasons_json='["Python classifier says reject."]',
                created_at=now,
            )
        )

        session.add(
            AIReview(
                id="ai-review-index-a",
                capture_run_id=capture.id,
                posting_id=posting_a.id,
                source_job_id="a",
                review_source="chatgpt_source_first",
                review_version="2026-08-27.1",
                contract_version="1.0",
                decision="strong_pursue",
                priority_score=95,
                geography_status="eligible",
                clearance_status="clear",
                language_status="clear",
                technical_fit=92,
                duplicate_of_posting_id=None,
                summary="Strong source-first fit.",
                reasons_json=json.dumps(
                    [
                        "Spain-compatible.",
                        "Strong application-support alignment.",
                    ]
                ),
                reviewed_at=now,
                imported_at=now,
            )
        )

        session.commit()

        result = list_ai_review_opportunity_index(session)

        assert len(result) == 2

        first = result[0]
        second = result[1]

        assert first.posting_id == posting_a.id
        assert first.ai_review_status == "reviewed"
        assert first.decision == "strong_pursue"
        assert first.priority_score == 95

        serialized = first.model_dump()

        assert "evaluation_id" not in serialized
        assert "recommendation" not in serialized
        assert "confidence" not in serialized
        assert "ranking_score" not in serialized

        assert second.posting_id == posting_b.id
        assert second.ai_review_status == "awaiting_ai_review"
        assert second.decision is None
        assert second.priority_score is None
    finally:
        session.close()


def test_ai_review_index_places_reject_below_awaiting(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"

    factory = create_session_factory(database_url)
    session = factory()
    now = datetime.now(UTC)

    try:
        sources = []
        postings = []

        for suffix in ("awaiting", "reject"):
            source = SourceDocument(
                id=f"source-{suffix}",
                source_type="linkedin",
                source_url=(f"https://linkedin.example/jobs/{suffix}"),
                raw_text=suffix,
                content_hash=("c" * 64 if suffix == "awaiting" else "d" * 64),
                captured_at=now,
            )

            posting = Posting(
                id=f"posting-{suffix}",
                source_document_id=source.id,
                canonical_url=source.source_url,
                identity_key=f"linkedin:{suffix}",
                title=suffix.title(),
                company="Example",
                location="Remote",
                description=suffix,
                identity_status="verified",
                created_at=now,
            )

            sources.append(source)
            postings.append(posting)

        capture = CaptureRun(
            id="capture-sort",
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

        session.add_all([*sources, capture])
        session.flush()

        session.add_all(postings)
        session.flush()

        for posting, source in zip(
            postings,
            sources,
            strict=True,
        ):
            session.add(
                CaptureItem(
                    id=f"item-{posting.id}",
                    capture_run_id=capture.id,
                    source_job_id=posting.id,
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

        rejected = next(posting for posting in postings if posting.id == "posting-reject")

        session.add(
            AIReview(
                id="ai-review-reject",
                capture_run_id=capture.id,
                posting_id=rejected.id,
                source_job_id=rejected.id,
                review_source="chatgpt_source_first",
                review_version="2026-08-27.1",
                contract_version="1.0",
                decision="reject",
                priority_score=0,
                geography_status="ineligible",
                clearance_status="clear",
                language_status="clear",
                technical_fit=90,
                duplicate_of_posting_id=None,
                summary="Foreign-only employment.",
                reasons_json='["Not employable from Spain."]',
                reviewed_at=now,
                imported_at=now,
            )
        )

        session.commit()

        result = list_ai_review_opportunity_index(session)

        assert [item.ai_review_status for item in result] == [
            "awaiting_ai_review",
            "reviewed",
        ]

        assert result[1].decision == "reject"
        assert result[1].priority_score == 0
    finally:
        session.close()
