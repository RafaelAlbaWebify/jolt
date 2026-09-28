from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jolt.database import (
    AIReview,
    Application,
    ApplicationEvent,
    CaptureItem,
    CaptureRun,
    LinkedInDiscoveryBatch,
    LinkedInDiscoveryBatchSearch,
    LinkedInSavedSearch,
    Posting,
    ReviewDecision,
    SourceDocument,
    create_session_factory,
)
from jolt.linkedin_search_performance import build_linkedin_search_performance


def _now() -> datetime:
    return datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_search_performance_tracks_real_funnel_without_counting_preparing_as_applied(
    tmp_path: Path,
) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'performance.db').as_posix()}")

    with factory() as session:
        search = LinkedInSavedSearch(
            id="search-1",
            label="Technical Support EU",
            search_url="https://www.linkedin.com/jobs/search/?keywords=Technical+Support",
            notes="",
            enabled=True,
            max_jobs=50,
            max_pages=5,
            created_at=_now(),
            updated_at=_now(),
        )
        batch = LinkedInDiscoveryBatch(
            id="batch-1",
            status="completed",
            selected_search_count=1,
            started_at=_now(),
            completed_at=_now(),
            created_at=_now(),
        )
        run = CaptureRun(
            id="capture-1",
            source="linkedin",
            mode="live",
            status="completed",
            search_url=search.search_url,
            warnings_json="[]",
            requested_item_limit=50,
            observed_item_count=2,
            stop_reason="requested_limit_reached",
            started_at=_now(),
            completed_at=_now(),
        )
        batch_search = LinkedInDiscoveryBatchSearch(
            id="batch-search-1",
            batch_id=batch.id,
            saved_search_id=search.id,
            position=1,
            label_snapshot=search.label,
            search_url_snapshot=search.search_url,
            max_jobs_snapshot=50,
            max_pages_snapshot=5,
            status="completed",
            capture_run_id=run.id,
            captured_count=2,
            verified_count=2,
            new_posting_count=2,
            duplicate_count=0,
            error="",
            started_at=_now(),
            completed_at=_now(),
        )
        session.add_all([search, batch, run, batch_search])
        session.flush()

        for index in (1, 2):
            source = SourceDocument(
                id=f"source-{index}",
                source_type="linkedin",
                source_url=f"https://www.linkedin.com/jobs/view/{index}",
                raw_text=f"Job {index}",
                content_hash=f"{index:064d}",
                captured_at=_now(),
            )
            posting = Posting(
                id=f"posting-{index}",
                source_document_id=source.id,
                canonical_url=source.source_url,
                identity_key=f"url:{source.source_url}",
                title=f"Job {index}",
                company="Example",
                location="Spain",
                description=f"Job {index}",
                identity_status="new",
                created_at=_now(),
            )
            item = CaptureItem(
                id=f"item-{index}",
                capture_run_id=run.id,
                source_job_id=str(index),
                source_url=source.source_url,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                detail_status="verified",
                verification_reasons_json="[]",
                source_document_id=source.id,
                posting_id=posting.id,
            )
            review = AIReview(
                id=f"ai-{index}",
                capture_run_id=run.id,
                posting_id=posting.id,
                source_job_id=str(index),
                review_source="chatgpt_source_first",
                review_version="test",
                contract_version="1.1",
                decision="pursue" if index == 1 else "reject",
                priority_score=90 if index == 1 else 0,
                geography_status="eligible",
                clearance_status="clear",
                language_status="clear",
                technical_fit=90 if index == 1 else None,
                hardline_status="PASS" if index == 1 else "REJECT",
                hardline_reasons_json="[]",
                location_eligibility="eligible",
                location_evidence_json="[]",
                mandatory_requirements_json="[]",
                mandatory_requirement_results_json="[]",
                employment_constraints_json="[]",
                fit_analysis_allowed=index == 1,
                decision_reason="test",
                duplicate_of_posting_id=None,
                summary="test",
                reasons_json="[]",
                reviewed_at=_now(),
                imported_at=_now(),
            )
            session.add(source)
            session.flush()
            session.add(posting)
            session.flush()
            session.add(item)
            session.flush()
            session.add(review)

        session.flush()

        for index in (1, 2):
            session.add(
                ReviewDecision(
                    id=f"human-{index}",
                    posting_id=f"posting-{index}",
                    evaluation_id=None,
                    ai_review_id=f"ai-{index}",
                    decision="pursue",
                    reason_code="",
                    notes="",
                    evaluation_overridden=False,
                    reviewed_at=_now(),
                )
            )
            application = Application(
                id=f"application-{index}",
                posting_id=f"posting-{index}",
                status="submitted" if index == 1 else "preparing",
                application_url="",
                resume_used="",
                notes="",
                created_at=_now(),
                updated_at=_now(),
            )
            session.add(application)

        session.flush()
        session.add(
            ApplicationEvent(
                id="event-submit",
                application_id="application-1",
                event_type="status_changed",
                from_status="preparing",
                to_status="submitted",
                notes="",
                occurred_at=_now(),
            )
        )
        session.commit()

        performance = build_linkedin_search_performance(session)

    assert len(performance) == 1
    item = performance[0]
    assert item.captured_count == 2
    assert item.new_posting_count == 2
    assert item.canonical_posting_count == 2
    assert item.ai_reviewed_count == 2
    assert item.ai_actionable_count == 1
    assert item.human_pursue_count == 2
    assert item.application_count == 2
    assert item.applied_count == 1
    assert item.interview_count == 0
    assert item.offer_count == 0
