from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from jolt.database import (
    CaptureRun,
    MarketIntelligenceObservation,
    create_session_factory,
)
from jolt.main import create_app


def _capture_payload(
    *,
    title: str,
    source_job_id: str,
) -> dict[str, object]:
    return {
        "search_url": "https://www.linkedin.com/jobs/search/?keywords=Support",
        "requested_item_limit": 1,
        "items": [
            {
                "source_job_id": source_job_id,
                "source_url": (f"https://www.linkedin.com/jobs/view/{source_job_id}/"),
                "title": title,
                "company": "Example Co",
                "location": "Spain (Remote)",
                "description": (
                    "Application Support role with Windows, SQL, "
                    "ServiceNow and production support responsibilities."
                ),
                "identity_verified": True,
                "verification_reason": "Fixture identity verified.",
            }
        ],
        "pages": [
            {
                "page_number": 1,
                "visible_job_ids": [source_job_id],
                "next_control_present": False,
                "next_control_enabled": False,
            }
        ],
    }


def test_completed_capture_extracts_durable_market_observation(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    captured = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Support Engineer",
            source_job_id="job-1",
        ),
    )
    assert captured.status_code == 200

    capture_run_id = captured.json()["capture_run_id"]

    factory = create_session_factory(database_url)
    with factory() as session:
        observation = session.scalar(
            select(MarketIntelligenceObservation).where(
                MarketIntelligenceObservation.source_capture_run_id == capture_run_id
            )
        )

        assert observation is not None
        assert observation.source_job_id == "job-1"
        assert observation.title == "Support Engineer"
        assert observation.description
        assert observation.posting_identity_key
        assert observation.captured_at is not None
        assert observation.observed_at is not None


def test_retention_preview_keeps_latest_and_marks_previous_complete_capture(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    first = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="First Support Engineer",
            source_job_id="job-old",
        ),
    ).json()

    second = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Second Support Engineer",
            source_job_id="job-current",
        ),
    ).json()

    preview_response = client.get("/api/data-management/retention-preview")
    assert preview_response.status_code == 200

    preview = preview_response.json()
    assert preview["capture_run_count"] == 2
    assert preview["superseded_capture_run_count"] == 1
    assert preview["market_observation_count"] == 2
    assert preview["current_capture_run_id"] == second["capture_run_id"]

    by_id = {item["capture_run_id"]: item for item in preview["captures"]}

    assert by_id[second["capture_run_id"]]["is_current_capture"] is True
    assert by_id[second["capture_run_id"]]["retention_action"] == "keep_current_capture"

    assert by_id[first["capture_run_id"]]["is_current_capture"] is False
    assert by_id[first["capture_run_id"]]["market_extraction_complete"] is True
    assert (
        by_id[first["capture_run_id"]]["retention_action"]
        == "purge_when_guarded_cleanup_is_enabled"
    )


def test_market_observation_has_no_foreign_key_to_raw_capture_run(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    captured = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Independent Observation",
            source_job_id="job-independent",
        ),
    ).json()

    factory = create_session_factory(database_url)

    with factory() as session:
        run = session.get(
            CaptureRun,
            captured["capture_run_id"],
        )
        assert run is not None

        observation = session.scalar(
            select(MarketIntelligenceObservation).where(
                MarketIntelligenceObservation.source_capture_run_id == run.id
            )
        )
        assert observation is not None

        fk_rows = (
            session.connection()
            .exec_driver_sql("PRAGMA foreign_key_list('market_intelligence_observations')")
            .fetchall()
        )

        assert all(row[2] != "capture_runs" for row in fk_rows)


def test_market_observation_extraction_is_idempotent(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    captured = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Idempotent Observation",
            source_job_id="job-idempotent",
        ),
    ).json()

    from jolt.market_intelligence_observations import (
        extract_market_intelligence_observations,
    )

    factory = create_session_factory(database_url)

    with factory() as session:
        created_again = extract_market_intelligence_observations(
            session,
            captured["capture_run_id"],
        )
        session.commit()

        observations = list(
            session.scalars(
                select(MarketIntelligenceObservation).where(
                    MarketIntelligenceObservation.source_capture_run_id
                    == captured["capture_run_id"]
                )
            ).all()
        )

        assert created_again == 0
        assert len(observations) == 1


def test_market_intelligence_uses_durable_archived_capture_observations(
    tmp_path,
) -> None:
    from jolt.capture_archival import archive_capture_run

    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    first = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Application Support Engineer",
            source_job_id="market-old",
        ),
    )
    assert first.status_code == 200

    second = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Cloud Support Engineer",
            source_job_id="market-current",
        ),
    )
    assert second.status_code == 200

    first_run_id = first.json()["capture_run_id"]

    factory = create_session_factory(database_url)
    with factory() as session:
        archived = archive_capture_run(
            session,
            first_run_id,
        )
        assert archived.capture_run_id == first_run_id

    response = client.get(
        "/api/market-intelligence",
        params={
            "timeframe": "all",
            "source_scope": "capture_batches",
        },
    )
    assert response.status_code == 200

    payload = response.json()

    assert payload["total_unique_roles"] == 2
    assert payload["evaluation_coverage"]["source_posting_count"] == 2
    assert "durable per-capture observations" in payload["fit_explanation"]


def test_captured_retained_posting_does_not_become_manual_after_capture_links_are_removed(
    tmp_path,
) -> None:
    from sqlalchemy import delete, select

    from jolt.capture_artifacts import CaptureArtifact
    from jolt.database import CaptureItem

    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    captured = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Persistent Captured Support Engineer",
            source_job_id="captured-retained",
        ),
    )
    assert captured.status_code == 200

    capture_run_id = captured.json()["capture_run_id"]

    factory = create_session_factory(database_url)

    with factory() as session:
        capture_item_ids = list(
            session.scalars(
                select(CaptureItem.id).where(CaptureItem.capture_run_id == capture_run_id)
            ).all()
        )

        if capture_item_ids:
            session.execute(
                delete(CaptureArtifact).where(CaptureArtifact.capture_item_id.in_(capture_item_ids))
            )

        session.execute(delete(CaptureItem).where(CaptureItem.capture_run_id == capture_run_id))
        session.commit()

    capture_scope = client.get(
        "/api/market-intelligence",
        params={
            "timeframe": "all",
            "source_scope": "capture_batches",
        },
    )
    assert capture_scope.status_code == 200
    assert capture_scope.json()["total_unique_roles"] == 1

    manual_scope = client.get(
        "/api/market-intelligence",
        params={
            "timeframe": "all",
            "source_scope": "manual_intake",
        },
    )
    assert manual_scope.status_code == 200
    assert manual_scope.json()["total_unique_roles"] == 0

    all_scope = client.get(
        "/api/market-intelligence",
        params={
            "timeframe": "all",
            "source_scope": "all",
        },
    )
    assert all_scope.status_code == 200
    assert all_scope.json()["total_unique_roles"] == 1


def test_repeated_capture_occurrences_are_filtered_before_deduplication(
    tmp_path,
) -> None:
    from datetime import UTC, datetime, timedelta

    from jolt.database import MarketIntelligenceObservation
    from jolt.market_intelligence import (
        _durable_capture_market_records,
        _filter_by_timeframe,
    )

    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    captured = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Repeated Support Engineer",
            source_job_id="repeat-job",
        ),
    )
    assert captured.status_code == 200

    factory = create_session_factory(database_url)

    with factory() as session:
        original = session.scalar(
            select(MarketIntelligenceObservation).where(
                MarketIntelligenceObservation.source_job_id == "repeat-job"
            )
        )
        assert original is not None

        now = datetime.now(UTC)

        original.captured_at = now - timedelta(days=45)

        repeated = MarketIntelligenceObservation(
            id="repeat-observation-newer",
            source_capture_run_id="repeat-run-newer",
            source_job_id="repeat-job-newer",
            posting_identity_key=original.posting_identity_key,
            source_url=original.source_url,
            title=original.title,
            company=original.company,
            location=original.location,
            description=original.description,
            engine_version=original.engine_version,
            recommendation=original.recommendation,
            confidence=original.confidence,
            ranking_score=original.ranking_score,
            reasons_json=original.reasons_json,
            captured_at=now - timedelta(days=5),
            observed_at=now,
        )
        session.add(repeated)
        session.commit()

        postings, evaluations = _durable_capture_market_records(session)

        assert len(postings) == 2
        assert len(evaluations) == 2

        recent = _filter_by_timeframe(
            postings,
            "last_30_days",
        )

        assert len(recent) == 1
        assert recent[0].id == repeated.id


def test_historical_market_observation_backfill_is_idempotent(
    tmp_path,
) -> None:
    from sqlalchemy import delete, func

    from jolt.market_intelligence_observations import (
        backfill_market_intelligence_observations,
    )

    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    first = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Historical Application Support Engineer",
            source_job_id="backfill-one",
        ),
    )
    second = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Historical Cloud Support Engineer",
            source_job_id="backfill-two",
        ),
    )

    assert first.status_code == 200
    assert second.status_code == 200

    factory = create_session_factory(database_url)

    with factory() as session:
        session.execute(delete(MarketIntelligenceObservation))
        session.commit()

        assert session.scalar(select(func.count(MarketIntelligenceObservation.id))) == 0

        first_result = backfill_market_intelligence_observations(session)
        session.commit()

        assert first_result["capture_run_count"] == 2
        assert first_result["created_observation_count"] == 2
        assert first_result["total_observation_count"] == 2

        second_result = backfill_market_intelligence_observations(session)
        session.commit()

        assert second_result["capture_run_count"] == 2
        assert second_result["created_observation_count"] == 0
        assert second_result["total_observation_count"] == 2


def test_observation_extraction_prefers_current_engine_evaluation(
    tmp_path,
) -> None:
    from datetime import timedelta

    from sqlalchemy import delete

    from jolt.database import (
        CaptureItem,
        Evaluation,
        utc_now,
    )
    from jolt.market_intelligence_observations import (
        backfill_market_intelligence_observations,
    )
    from jolt.strategy_runtime import ENGINE_VERSION

    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    captured = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Engine Preference Support Engineer",
            source_job_id="engine-preference",
        ),
    )
    assert captured.status_code == 200

    factory = create_session_factory(database_url)

    with factory() as session:
        item = session.scalar(
            select(CaptureItem).where(CaptureItem.source_job_id == "engine-preference")
        )
        assert item is not None
        assert item.posting_id is not None

        baseline = session.scalar(
            select(Evaluation)
            .where(Evaluation.posting_id == item.posting_id)
            .order_by(
                Evaluation.created_at.desc(),
                Evaluation.id.desc(),
            )
        )
        assert baseline is not None

        now = utc_now()

        current = Evaluation(
            id="current-engine-evaluation",
            posting_id=item.posting_id,
            profile_version_id=baseline.profile_version_id,
            engine_version=ENGINE_VERSION,
            recommendation="pursue",
            confidence="medium",
            ranking_score=73,
            reasons_json='["current-engine-test"]',
            created_at=now,
        )

        newer_fallback = Evaluation(
            id="newer-fallback-evaluation",
            posting_id=item.posting_id,
            profile_version_id=baseline.profile_version_id,
            engine_version="legacy-test-engine",
            recommendation="reject",
            confidence="high",
            ranking_score=1,
            reasons_json='["newer-fallback-test"]',
            created_at=now + timedelta(minutes=1),
        )

        session.add(current)
        session.add(newer_fallback)

        session.execute(
            delete(MarketIntelligenceObservation).where(
                MarketIntelligenceObservation.source_job_id == "engine-preference"
            )
        )
        session.commit()

        result = backfill_market_intelligence_observations(session)
        session.commit()

        assert result["created_observation_count"] == 1

        rebuilt = session.scalar(
            select(MarketIntelligenceObservation).where(
                MarketIntelligenceObservation.source_job_id == "engine-preference"
            )
        )

        assert rebuilt is not None
        assert rebuilt.engine_version == ENGINE_VERSION
        assert rebuilt.recommendation == "pursue"
        assert rebuilt.confidence == "medium"
        assert rebuilt.ranking_score == 73
        assert rebuilt.reasons_json == '["current-engine-test"]'


def test_guarded_retention_cleanup_preserves_owned_state_and_market_history(
    tmp_path,
) -> None:
    from jolt.database import (
        Application,
        CaptureItem,
        CaptureRun,
        MarketIntelligenceObservation,
        Posting,
        SourceDocument,
        utc_now,
    )
    from jolt.retention_ownership import (
        build_guarded_retention_cleanup_plan,
        execute_guarded_retention_cleanup,
    )

    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    disposable_capture = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Disposable Historical Support Engineer",
            source_job_id="cleanup-disposable",
        ),
    )
    retained_capture = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Retained Historical Support Engineer",
            source_job_id="cleanup-retained",
        ),
    )
    current_capture = client.post(
        "/api/captures/linkedin/live",
        json=_capture_payload(
            title="Current Support Engineer",
            source_job_id="cleanup-current",
        ),
    )

    assert disposable_capture.status_code == 200
    assert retained_capture.status_code == 200
    assert current_capture.status_code == 200

    factory = create_session_factory(database_url)

    with factory() as session:
        disposable_item = session.scalar(
            select(CaptureItem).where(CaptureItem.source_job_id == "cleanup-disposable")
        )
        retained_item = session.scalar(
            select(CaptureItem).where(CaptureItem.source_job_id == "cleanup-retained")
        )
        current_item = session.scalar(
            select(CaptureItem).where(CaptureItem.source_job_id == "cleanup-current")
        )

        assert disposable_item is not None
        assert retained_item is not None
        assert current_item is not None
        assert disposable_item.posting_id is not None
        assert retained_item.posting_id is not None
        assert current_item.posting_id is not None
        assert disposable_item.source_document_id is not None
        assert retained_item.source_document_id is not None

        disposable_posting_id = disposable_item.posting_id
        retained_posting_id = retained_item.posting_id
        current_posting_id = current_item.posting_id

        disposable_source_id = disposable_item.source_document_id
        retained_source_id = retained_item.source_document_id

        disposable_run = session.get(
            CaptureRun,
            disposable_item.capture_run_id,
        )
        retained_run = session.get(
            CaptureRun,
            retained_item.capture_run_id,
        )

        assert disposable_run is not None
        assert retained_run is not None

        assert disposable_run.status != "archived"
        assert retained_run.status != "archived"

        now = utc_now()

        session.add(
            Application(
                id="cleanup-retained-application",
                posting_id=retained_posting_id,
                status="applied",
                application_url="",
                resume_used="",
                notes="",
                created_at=now,
                updated_at=now,
            )
        )

        session.commit()

        plan = build_guarded_retention_cleanup_plan(session)

        assert plan["blocked"] is False
        assert plan["superseded_capture_run_count"] == 2
        assert plan["capture_only_posting_count"] == 1
        assert plan["retained_posting_count"] == 1
        assert plan["missing_market_observation_count"] == 0

        before_candidate = session.get(
            Posting,
            disposable_posting_id,
        )
        assert before_candidate is not None

        try:
            execute_guarded_retention_cleanup(
                session,
                confirmation="WRONG CONFIRMATION",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Wrong confirmation must block cleanup.")

        assert (
            session.get(
                Posting,
                disposable_posting_id,
            )
            is not None
        )

        result = execute_guarded_retention_cleanup(
            session,
            confirmation=str(plan["required_confirmation"]),
        )
        session.commit()

        assert result["deleted"]["capture_runs"] == 2
        assert result["deleted"]["postings"] == 1
        assert result["preserved_retained_posting_count"] == 1

        assert (
            session.get(
                Posting,
                disposable_posting_id,
            )
            is None
        )

        assert (
            session.get(
                SourceDocument,
                disposable_source_id,
            )
            is None
        )

        assert (
            session.get(
                Posting,
                retained_posting_id,
            )
            is not None
        )

        assert (
            session.get(
                SourceDocument,
                retained_source_id,
            )
            is not None
        )

        assert (
            session.get(
                Posting,
                current_posting_id,
            )
            is not None
        )

        assert (
            session.get(
                CaptureRun,
                current_item.capture_run_id,
            )
            is not None
        )

        retained_application = session.get(
            Application,
            "cleanup-retained-application",
        )
        assert retained_application is not None

        historical_observation = session.scalar(
            select(MarketIntelligenceObservation).where(
                MarketIntelligenceObservation.source_job_id == "cleanup-disposable"
            )
        )
        assert historical_observation is not None
