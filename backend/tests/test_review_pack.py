from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

from jolt.database import (
    Application,
    CaptureItem,
    CapturePage,
    CaptureRun,
    Evaluation,
    MarketIntelligenceObservation,
    Posting,
    ProfileVersion,
    ReviewDecision,
    SourceDocument,
    create_session_factory,
)
from jolt.review_pack import build_review_pack


def test_review_pack_contains_latest_capture_evidence_classification_market_and_lineage(
    tmp_path,
) -> None:
    session_factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")
    session = session_factory()
    now = datetime.now(UTC)

    try:
        source = SourceDocument(
            id="source-1",
            source_type="linkedin",
            source_url="https://linkedin.example/jobs/123",
            raw_text="Full captured job evidence with Windows, SQL and REST API.",
            content_hash="a" * 64,
            captured_at=now,
        )

        posting = Posting(
            id="posting-1",
            source_document_id=source.id,
            canonical_url=source.source_url,
            identity_key="linkedin:123",
            title="Technical Support Engineer",
            company="Example",
            location="Spain · Remote",
            description="Windows SQL REST API technical support role.",
            identity_status="verified",
            created_at=now,
        )

        profile = ProfileVersion(
            id="profile-1",
            profile_id="rafael",
            version=1,
            configuration_json='{"target":"technical support"}',
            created_at=now,
        )

        evaluation = Evaluation(
            id="evaluation-1",
            posting_id=posting.id,
            profile_version_id=profile.id,
            engine_version="test-engine",
            recommendation="pursue",
            confidence="high",
            ranking_score=84,
            reasons_json='["Verified fit reason"]',
            created_at=now,
        )

        capture = CaptureRun(
            id="capture-1",
            source="linkedin",
            mode="supervised_live",
            status="completed",
            search_url="https://linkedin.example/jobs/search",
            warnings_json="[]",
            requested_item_limit=25,
            observed_item_count=1,
            stop_reason="requested_limit_reached",
            started_at=now,
            completed_at=now,
        )

        page = CapturePage(
            id="page-1",
            capture_run_id=capture.id,
            page_number=1,
            visible_job_ids_json='["123"]',
            next_control_present=True,
            next_control_enabled=True,
        )

        item = CaptureItem(
            id="item-1",
            capture_run_id=capture.id,
            source_job_id="123",
            source_url=source.source_url,
            title=posting.title,
            company=posting.company,
            location=posting.location,
            detail_status="verified",
            verification_reasons_json="[]",
            source_document_id=source.id,
            posting_id=posting.id,
        )

        review = ReviewDecision(
            id="review-1",
            posting_id=posting.id,
            evaluation_id=evaluation.id,
            decision="pursue",
            reason_code="",
            notes="Keep",
            evaluation_overridden=False,
            reviewed_at=now,
        )

        application = Application(
            id="application-1",
            posting_id=posting.id,
            status="preparing",
            application_url="",
            resume_used="",
            notes="",
            created_at=now,
            updated_at=now,
        )

        observation = MarketIntelligenceObservation(
            id="observation-1",
            source_capture_run_id=capture.id,
            source_job_id="123",
            posting_identity_key=posting.identity_key,
            source_url=source.source_url,
            title=posting.title,
            company=posting.company,
            location=posting.location,
            description=posting.description,
            engine_version=evaluation.engine_version,
            recommendation=evaluation.recommendation,
            confidence=evaluation.confidence,
            ranking_score=evaluation.ranking_score,
            reasons_json=evaluation.reasons_json,
            captured_at=now,
            observed_at=now,
        )

        session.add_all(
            [
                source,
                profile,
                capture,
            ]
        )
        session.flush()

        session.add(posting)
        session.flush()

        session.add_all(
            [
                evaluation,
                page,
                item,
                observation,
            ]
        )
        session.flush()

        session.add_all(
            [
                review,
                application,
            ]
        )
        session.commit()

        payload = build_review_pack(session)

        with ZipFile(BytesIO(payload)) as archive:
            names = set(archive.namelist())

            required = {
                "manifest.json",
                "capture/run.json",
                "capture/pages.json",
                "jobs/jobs.json",
                "jobs/jolt_classifications.json",
                "jobs/state.json",
                "profile/profile_versions.json",
                "evidence/source_documents.json",
                "audit/lineage.json",
                "audit/review_decisions.json",
                "audit/outcomes.json",
                "market/latest_capture_observations.json",
                "market/current_views.json",
            }

            assert required.issubset(names)

            manifest = json.loads(archive.read("manifest.json"))
            jobs = json.loads(archive.read("jobs/jobs.json"))
            classifications = json.loads(archive.read("jobs/jolt_classifications.json"))
            lineage = json.loads(archive.read("audit/lineage.json"))
            market = json.loads(archive.read("market/current_views.json"))
            observations = json.loads(archive.read("market/latest_capture_observations.json"))

        assert manifest["latest_capture_id"] == capture.id
        assert manifest["counts"]["capture_items"] == 1
        assert manifest["counts"]["market_observations"] == 1

        assert jobs[0]["source_job_id"] == "123"
        assert "Full captured job evidence" in jobs[0]["source_raw_text"]
        assert jobs[0]["description"] == posting.description

        assert classifications[0]["effective_evaluation"]["recommendation"] == "pursue"
        assert classifications[0]["effective_evaluation"]["ranking_score"] == 84
        assert classifications[0]["effective_evaluation"]["reasons"] == ["Verified fit reason"]

        assert lineage[0]["capture_item_id"] == item.id
        assert lineage[0]["posting_id"] == posting.id
        assert lineage[0]["effective_evaluation_id"] == evaluation.id
        assert lineage[0]["market_observation_ids"] == [observation.id]

        assert observations[0]["source_job_id"] == "123"
        assert market["latest_capture_id"] == capture.id
        assert market["capture_batches_view"]["total_unique_roles"] == 1
    finally:
        session.close()
