from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jolt.database import (
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
from jolt.linkedin_batch_review import (
    BatchAIReviewImportRequest,
    build_batch_ai_review_document,
    import_batch_ai_review,
)


def _factory(tmp_path: Path):
    return create_session_factory(f"sqlite:///{(tmp_path / 'batch-review.db').as_posix()}")


def _now() -> datetime:
    return datetime.now(UTC)


def _seed_completed_batch(session) -> str:
    now = _now()
    searches = [
        LinkedInSavedSearch(
            id="search-1",
            label="LinkedIn IT Support",
            search_url="https://www.linkedin.com/jobs/search/?keywords=IT+Support",
            notes="",
            enabled=True,
            max_jobs=100,
            max_pages=10,
            created_at=now,
            updated_at=now,
        ),
        LinkedInSavedSearch(
            id="search-2",
            label="LinkedIn Application Support",
            search_url="https://www.linkedin.com/jobs/search/?keywords=Application+Support",
            notes="",
            enabled=True,
            max_jobs=100,
            max_pages=10,
            created_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(searches)

    batch = LinkedInDiscoveryBatch(
        id="batch-1",
        status="completed",
        selected_search_count=2,
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    session.add(batch)

    capture_runs = []
    for index in (1, 2):
        capture_runs.append(
            CaptureRun(
                id=f"capture-{index}",
                source="linkedin",
                mode="live",
                status="completed",
                search_url=searches[index - 1].search_url,
                warnings_json="[]",
                requested_item_limit=100,
                observed_item_count=2,
                stop_reason="no_next_page",
                started_at=now,
                completed_at=now,
            )
        )
    session.add_all(capture_runs)
    session.flush()

    for index in (1, 2):
        session.add(
            LinkedInDiscoveryBatchSearch(
                id=f"batch-search-{index}",
                batch_id=batch.id,
                saved_search_id=searches[index - 1].id,
                position=index,
                label_snapshot=searches[index - 1].label,
                search_url_snapshot=searches[index - 1].search_url,
                max_jobs_snapshot=100,
                max_pages_snapshot=10,
                status="completed",
                capture_run_id=f"capture-{index}",
                captured_count=2,
                verified_count=2,
                new_posting_count=2,
                duplicate_count=0,
                error="",
                started_at=now,
                completed_at=now,
            )
        )

    for index in (1, 2):
        source = SourceDocument(
            id=f"source-{index}",
            source_type="linkedin",
            source_url=f"https://www.linkedin.com/jobs/view/{index}/",
            raw_text=f"Full vacancy evidence {index}",
            content_hash=f"{index}" * 64,
            captured_at=now,
        )
        posting = Posting(
            id=f"posting-{index}",
            source_document_id=source.id,
            canonical_url=source.source_url,
            identity_key=f"linkedin:{index}",
            title=f"Support Engineer {index}",
            company="Example Corp",
            location="Spain",
            description=f"Description {index}",
            identity_status="canonical",
            created_at=now,
        )
        session.add_all([source, posting])

    session.flush()

    session.add_all(
        [
            CaptureItem(
                id="item-1a",
                capture_run_id="capture-1",
                source_job_id="job-1",
                source_url="https://www.linkedin.com/jobs/view/1/",
                title="Support Engineer 1",
                company="Example Corp",
                location="Spain",
                detail_status="verified",
                verification_reasons_json="[]",
                source_document_id="source-1",
                posting_id="posting-1",
            ),
            CaptureItem(
                id="item-1b",
                capture_run_id="capture-2",
                source_job_id="job-1",
                source_url="https://www.linkedin.com/jobs/view/1/",
                title="Support Engineer 1",
                company="Example Corp",
                location="Spain",
                detail_status="verified",
                verification_reasons_json="[]",
                source_document_id="source-1",
                posting_id="posting-1",
            ),
            CaptureItem(
                id="item-2",
                capture_run_id="capture-2",
                source_job_id="job-2",
                source_url="https://www.linkedin.com/jobs/view/2/",
                title="Support Engineer 2",
                company="Example Corp",
                location="Spain",
                detail_status="verified",
                verification_reasons_json="[]",
                source_document_id="source-2",
                posting_id="posting-2",
            ),
        ]
    )
    session.commit()
    return batch.id


def _review_job(posting_id: str, source_job_id: str) -> dict[str, object]:
    return {
        "posting_id": posting_id,
        "source_job_id": source_job_id,
        "hardline_status": "PASS",
        "hardline_reasons": [],
        "location_eligibility": "eligible",
        "location_evidence": ["Spain"],
        "mandatory_requirements": [],
        "mandatory_requirement_results": [],
        "employment_constraints": [],
        "fit_analysis_allowed": True,
        "technical_fit_percent": 80,
        "final_decision": "pursue",
        "decision_reason": "Good fit",
        "decision": "pursue",
        "priority_score": 80,
        "geography_status": "eligible",
        "clearance_status": "clear",
        "language_status": "clear",
        "technical_fit": 80,
        "duplicate_of_posting_id": None,
        "summary": "Good fit",
        "reasons": ["Relevant support experience"],
    }


def test_batch_review_export_deduplicates_postings_and_preserves_occurrences(
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        batch_id = _seed_completed_batch(session)
        document = build_batch_ai_review_document(session, batch_id)

        assert document["counts"] == {
            "raw_capture_items": 3,
            "unique_canonical_postings": 2,
            "already_reviewed_excluded": 0,
            "review_set": 2,
        }
        jobs = document["jobs"]
        assert isinstance(jobs, list)
        assert [job["posting_id"] for job in jobs] == ["posting-1", "posting-2"]
        assert len(jobs[0]["occurrences"]) == 2
        assert {item["search_label"] for item in jobs[0]["occurrences"]} == {
            "LinkedIn IT Support",
            "LinkedIn Application Support",
        }

        second = build_batch_ai_review_document(session, batch_id)
        assert [job["posting_id"] for job in second["jobs"]] == [
            "posting-1",
            "posting-2",
        ]
    finally:
        session.close()


def test_batch_review_import_requires_exact_frozen_set(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        batch_id = _seed_completed_batch(session)
        build_batch_ai_review_document(session, batch_id)

        incomplete = BatchAIReviewImportRequest.model_validate(
            {
                "contract_type": "jolt_ai_review_batch",
                "contract_version": "1.0",
                "ai_review_contract_version": "1.1",
                "discovery_batch_id": batch_id,
                "review_source": "chatgpt_source_first",
                "review_version": "test-v1",
                "reviewed_at": _now().isoformat(),
                "jobs": [_review_job("posting-1", "job-1")],
            }
        )
        with pytest.raises(ValueError, match="exactly one result"):
            import_batch_ai_review(session, incomplete)

        complete = BatchAIReviewImportRequest.model_validate(
            {
                "contract_type": "jolt_ai_review_batch",
                "contract_version": "1.0",
                "ai_review_contract_version": "1.1",
                "discovery_batch_id": batch_id,
                "review_source": "chatgpt_source_first",
                "review_version": "test-v1",
                "reviewed_at": _now().isoformat(),
                "jobs": [
                    _review_job("posting-1", "job-1"),
                    _review_job("posting-2", "job-2"),
                ],
            }
        )
        result = import_batch_ai_review(session, complete)
        assert result.received_count == 2
        assert result.created_count == 2
        assert result.updated_count == 0

        retry = import_batch_ai_review(session, complete)
        assert retry.created_count == 0
        assert retry.updated_count == 2
    finally:
        session.close()


def test_batch_review_recovers_verified_posting_from_earlier_failed_batch(
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        batch_id = _seed_completed_batch(session)
        good_batch = session.get(LinkedInDiscoveryBatch, batch_id)
        assert good_batch is not None
        earlier = good_batch.created_at - timedelta(hours=1)

        failed_batch = LinkedInDiscoveryBatch(
            id="failed-batch",
            status="failed",
            selected_search_count=1,
            started_at=earlier,
            completed_at=earlier,
            created_at=earlier,
        )
        failed_capture = CaptureRun(
            id="failed-capture",
            source="linkedin",
            mode="live",
            status="completed",
            search_url="https://www.linkedin.com/jobs/search/?keywords=Orphan",
            warnings_json="[]",
            requested_item_limit=100,
            observed_item_count=1,
            stop_reason="error",
            started_at=earlier,
            completed_at=earlier,
        )
        source = SourceDocument(
            id="orphan-source",
            source_type="linkedin",
            source_url="https://www.linkedin.com/jobs/view/orphan/",
            raw_text="Verified orphan vacancy evidence",
            content_hash="a" * 64,
            captured_at=earlier,
        )
        posting = Posting(
            id="orphan-posting",
            source_document_id=source.id,
            canonical_url=source.source_url,
            identity_key="linkedin:orphan",
            title="Orphan Support Engineer",
            company="Example Corp",
            location="Spain",
            description="Orphan description",
            identity_status="canonical",
            created_at=earlier,
        )
        session.add_all([failed_batch, failed_capture, source, posting])
        session.flush()
        session.add(
            LinkedInDiscoveryBatchSearch(
                id="failed-search",
                batch_id=failed_batch.id,
                saved_search_id="search-1",
                position=1,
                label_snapshot="Failed search",
                search_url_snapshot=failed_capture.search_url,
                max_jobs_snapshot=100,
                max_pages_snapshot=10,
                status="completed",
                capture_run_id=failed_capture.id,
                captured_count=1,
                verified_count=1,
                new_posting_count=1,
                duplicate_count=0,
                error="",
                started_at=earlier,
                completed_at=earlier,
            )
        )
        session.add(
            CaptureItem(
                id="orphan-item",
                capture_run_id=failed_capture.id,
                source_job_id="orphan-job",
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

        document = build_batch_ai_review_document(session, batch_id)
        jobs = document["jobs"]
        assert isinstance(jobs, list)
        assert {job["posting_id"] for job in jobs} == {
            "posting-1",
            "posting-2",
            "orphan-posting",
        }
        assert document["counts"] == {
            "raw_capture_items": 3,
            "unique_canonical_postings": 3,
            "already_reviewed_excluded": 0,
            "review_set": 3,
        }

        # The set is frozen after first materialization.
        second = build_batch_ai_review_document(session, batch_id)
        assert [job["posting_id"] for job in second["jobs"]] == [
            job["posting_id"] for job in jobs
        ]
    finally:
        session.close()


def test_batch_review_excludes_postings_with_human_decisions(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        batch_id = _seed_completed_batch(session)
        session.add(
            ReviewDecision(
                id="human-decision",
                posting_id="posting-1",
                evaluation_id=None,
                ai_review_id=None,
                decision="reject",
                reason_code="human",
                notes="Human state must be protected from AI review export.",
                evaluation_overridden=False,
                reviewed_at=_now(),
            )
        )
        session.commit()

        document = build_batch_ai_review_document(session, batch_id)
        jobs = document["jobs"]
        assert isinstance(jobs, list)
        assert [job["posting_id"] for job in jobs] == ["posting-2"]
        assert document["counts"] == {
            "raw_capture_items": 3,
            "unique_canonical_postings": 2,
            "already_reviewed_excluded": 1,
            "review_set": 1,
        }
    finally:
        session.close()
