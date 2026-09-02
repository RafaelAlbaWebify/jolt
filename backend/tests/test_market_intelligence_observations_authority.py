from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from jolt.database import (
    CaptureItem,
    CaptureRun,
    Evaluation,
    MarketIntelligenceObservation,
    Posting,
    ProfileVersion,
    SourceDocument,
    create_session_factory,
)
from jolt.market_intelligence_observations import extract_market_intelligence_observations


def test_market_observations_do_not_persist_local_evaluation_authority(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    source = SourceDocument(
        id="observation-source",
        source_type="linkedin",
        source_url="https://www.linkedin.com/jobs/view/123/",
        raw_text="CURRENT source evidence\nTechnical Support Engineer\nSQL API logs",
        content_hash="a" * 64,
        captured_at=now,
    )
    capture = CaptureRun(
        id="observation-capture",
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
    profile = ProfileVersion(
        id="profile-v1",
        profile_id="candidate",
        version=1,
        configuration_json="{}",
        created_at=now,
    )
    session.add_all([source, capture, profile])
    session.flush()
    posting = Posting(
        id="observation-posting",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="linkedin:123",
        title="Technical Support Engineer",
        company="Example",
        location="Remote",
        description="STALE canonical description",
        identity_status="verified",
        created_at=now,
    )
    session.add(posting)
    session.flush()
    session.add_all(
        [
            CaptureItem(
                id="observation-item",
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
            ),
            Evaluation(
                id="local-evaluation",
                posting_id=posting.id,
                profile_version_id=profile.id,
                engine_version="legacy-local-engine",
                recommendation="reject",
                confidence="high",
                ranking_score=1,
                reasons_json='["LOCAL JUDGMENT MUST NOT ENTER MARKET EVIDENCE"]',
                created_at=now,
            ),
        ]
    )
    session.commit()

    try:
        assert extract_market_intelligence_observations(session, capture.id) == 1
        session.commit()
        observation = session.scalar(select(MarketIntelligenceObservation))
        assert observation is not None
        assert observation.description == source.raw_text
        assert observation.engine_version == ""
        assert observation.recommendation == ""
        assert observation.confidence == ""
        assert observation.ranking_score is None
        assert observation.reasons_json == "[]"
    finally:
        session.close()
