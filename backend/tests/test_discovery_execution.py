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
