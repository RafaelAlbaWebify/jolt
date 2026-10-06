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
                    source="jobgether",
                    saved_search_id="not-used",
                ),
            )
        except ValueError as exc:
            assert "Indeed" in str(exc)
        else:
            raise AssertionError("Expected non-Indeed execution to be rejected.")
