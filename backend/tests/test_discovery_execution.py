from __future__ import annotations

from pathlib import Path

from jolt.database import create_session_factory
from jolt.discovery_execution import (
    DiscoveryExecutionCreateRequest,
    create_discovery_execution,
    execute_discovery_execution,
    get_discovery_execution,
)
from jolt.discovery_searches import DiscoverySavedSearchRequest, create_discovery_search


def _session(tmp_path: Path):
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'execution.db').as_posix()}")
    return factory()


def test_indeed_execution_persists_lifecycle_and_capture_run(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        search = create_discovery_search(
            session,
            DiscoverySavedSearchRequest(
                source="indeed",
                label="Indeed Application Support Spain",
                definition={
                    "search_url": "https://es.indeed.com/jobs?q=application+support",
                    "max_pages": 3,
                },
                enabled=True,
                max_jobs=30,
            ),
        )
        execution = create_discovery_execution(
            session,
            DiscoveryExecutionCreateRequest(
                source="indeed",
                saved_search_id=search.id,
            ),
        )
        assert execution.status == "queued"
        assert execution.target_jobs == 30
        assert execution.max_pages == 3
        assert execution.current_page == 0
        assert execution.pages_visited == 0
        assert execution.captured_count == 0

        execute_discovery_execution(
            session,
            execution.id,
            runner=lambda saved_search, execution_id: "capture-run-123",
        )

        finished = get_discovery_execution(session, execution.id)
        assert finished.status == "completed"
        assert finished.capture_run_id == "capture-run-123"
        assert finished.error == ""
        assert finished.started_at is not None
        assert finished.completed_at is not None


def test_execution_rejects_non_indeed_source(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        try:
            create_discovery_execution(
                session,
                DiscoveryExecutionCreateRequest(
                    source="linkedin",
                    saved_search_id="not-used",
                ),
            )
        except ValueError as exc:
            assert "Indeed" in str(exc)
        else:
            raise AssertionError("Expected non-Indeed execution to be rejected.")


def test_infojobs_execution_uses_saved_search_lifecycle(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        search = create_discovery_search(
            session,
            DiscoverySavedSearchRequest(
                source="infojobs",
                label="InfoJobs IT Support",
                definition={
                    "search_url": "https://www.infojobs.net/ofertas-trabajo/support-it",
                    "max_pages": 1,
                },
                max_jobs=5,
            ),
        )
        execution = create_discovery_execution(
            session,
            DiscoveryExecutionCreateRequest(source="infojobs", saved_search_id=search.id),
        )
        assert execution.status == "queued"
        execute_discovery_execution(
            session,
            execution.id,
            runner=lambda saved_search, execution_id: "infojobs-capture-123",
        )
        finished = get_discovery_execution(session, execution.id)
        assert finished.status == "completed"
        assert finished.capture_run_id == "infojobs-capture-123"


def test_infojobs_runner_rejects_untrusted_search_url(tmp_path: Path) -> None:
    from jolt.database import DiscoverySavedSearch, utc_now
    from jolt.discovery_execution import run_infojobs_saved_search

    search = DiscoverySavedSearch(
        id="untrusted-search",
        source="infojobs",
        label="Untrusted",
        definition_json='{"search_url":"https://example.com/job"}',
        definition_key="untrusted",
        notes="",
        enabled=True,
        max_jobs=5,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    try:
        run_infojobs_saved_search(search, "test-no-browser-launch")
    except ValueError as exc:
        assert "InfoJobs listing URL" in str(exc)
    else:
        raise AssertionError("Expected cross-site URL to be rejected.")


def test_jobgether_saved_search_uses_existing_execution_lifecycle(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        search = create_discovery_search(
            session,
            DiscoverySavedSearchRequest(
                source="jobgether",
                label="Jobgether remote support",
                definition={"search_url": "https://jobgether.com/talent/matches", "max_pages": 1},
                max_jobs=5,
            ),
        )
        execution = create_discovery_execution(
            session,
            DiscoveryExecutionCreateRequest(source="jobgether", saved_search_id=search.id),
        )
        assert execution.max_pages == 1
        assert execution.target_jobs == 5
        execute_discovery_execution(
            session,
            execution.id,
            runner=lambda saved_search, execution_id: "jobgether-run",
        )
        assert get_discovery_execution(session, execution.id).capture_run_id == "jobgether-run"


def test_indeed_known_only_evidence_is_completed_without_capture_run(tmp_path: Path) -> None:
    import json
    import zipfile

    from jolt.discovery_execution import _capture_run_id

    evidence = tmp_path / "indeed_capture.zip"
    with zipfile.ZipFile(evidence, "w") as archive:
        archive.writestr(
            "api_result.json",
            json.dumps(
                {
                    "submitted": False,
                    "status": "no_new_jobs",
                    "reason": "all_visible_offers_previously_verified",
                    "unique_visible_count": 8,
                    "unique_known_count": 8,
                    "capture_run_id": None,
                }
            ),
        )
    assert _capture_run_id(evidence) is None


def test_indeed_other_unpersisted_capture_remains_failure(tmp_path: Path) -> None:
    import json
    import zipfile

    import pytest

    from jolt.discovery_execution import _capture_run_id

    evidence = tmp_path / "indeed_capture.zip"
    with zipfile.ZipFile(evidence, "w") as archive:
        archive.writestr(
            "api_result.json",
            json.dumps(
                {
                    "submitted": False,
                    "status": "no_captured_jobs",
                    "reason": "no_new_extractable_offers",
                    "unique_visible_count": 9,
                    "capture_run_id": None,
                }
            ),
        )
    with pytest.raises(RuntimeError, match="did not persist"):
        _capture_run_id(evidence)


def test_discovery_runner_can_finish_without_new_capture(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        search = create_discovery_search(
            session,
            DiscoverySavedSearchRequest(
                source="indeed",
                label="Known-only Indeed",
                definition={
                    "search_url": "https://es.indeed.com/jobs?q=IT+support&l=Vigo",
                    "max_pages": 1,
                },
                max_jobs=10,
            ),
        )
        execution = create_discovery_execution(
            session,
            DiscoveryExecutionCreateRequest(source="indeed", saved_search_id=search.id),
        )
        execute_discovery_execution(session, execution.id, runner=lambda _search, _id: None)
        finished = get_discovery_execution(session, execution.id)
        assert finished.status == "completed"
        assert finished.capture_run_id is None
