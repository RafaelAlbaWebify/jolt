from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from jolt import linkedin_discovery_batch
from jolt.database import CaptureRun, create_session_factory, session_scope, utc_now
from jolt.linkedin_discovery_batch import execute_discovery_batch, schedule_discovery_batch
from jolt.linkedin_search_portfolio import (
    DiscoveryBatchCreateRequest,
    SavedLinkedInSearchRequest,
    create_discovery_batch,
    create_saved_linkedin_search,
    get_discovery_batch,
)


def _factory(tmp_path: Path):
    return create_session_factory(f"sqlite:///{(tmp_path / 'batch.db').as_posix()}")


@contextmanager
def _session(factory):
    scope = session_scope(factory)
    session = next(scope)
    try:
        yield session
    finally:
        scope.close()


def _saved_search(session, label: str, keywords: str):
    return create_saved_linkedin_search(
        session,
        SavedLinkedInSearchRequest(
            label=label,
            search_url=(
                "https://www.linkedin.com/jobs/search/"
                f"?f_TPR=r604800&f_WT=2&geoId=91000000&keywords={keywords}&sortBy=DD"
            ),
        ),
    )


def _capture_run(session, search_url: str) -> str:
    run = CaptureRun(
        id=f"capture-{abs(hash(search_url))}",
        source="linkedin",
        mode="live",
        status="completed",
        search_url=search_url,
        warnings_json="[]",
        requested_item_limit=100,
        observed_item_count=2,
        stop_reason="no_next_page",
        started_at=utc_now(),
        completed_at=utc_now(),
    )
    session.add(run)
    session.commit()
    return run.id


def _write_package(
    output_zip: Path,
    *,
    capture_run_id: str,
    duplicate_count: int,
) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    items = [
        {"identity_status": "confirmed_duplicate" if index < duplicate_count else "new"}
        for index in range(2)
    ]
    with zipfile.ZipFile(output_zip, "w") as archive:
        archive.writestr(
            "capture_summary.json",
            json.dumps(
                {
                    "captured_count": 2,
                    "verified_count": 2,
                    "stop_reason": "no_next_page",
                    "pages": [{"page_number": 1}],
                    "skipped_cards": [],
                    "retry_metrics": {"retry_attempted_count": 0},
                }
            ),
        )
        archive.writestr(
            "api_result.json",
            json.dumps(
                {
                    "capture_run_id": capture_run_id,
                    "items": items,
                }
            ),
        )


def test_batch_runs_two_searches_in_one_browser_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)

    with _session(factory) as session:
        first = _saved_search(session, "LinkedIn IT Support", "IT%20Support")
        second = _saved_search(
            session,
            "LinkedIn Application Support Engineer",
            "Application%20Support%20Engineer",
        )
        first_capture = _capture_run(session, first.search_url)
        second_capture = _capture_run(session, second.search_url)
        batch = create_discovery_batch(
            session,
            DiscoveryBatchCreateRequest(saved_search_ids=[first.id, second.id]),
        )
        schedule_discovery_batch(session, batch.id)

    browser_sessions = 0
    capture_ids = iter([first_capture, second_capture])

    @contextmanager
    def fake_browser(_profile_dir: Path) -> Iterator[tuple[object, object]]:
        nonlocal browser_sessions
        browser_sessions += 1
        yield object(), object()

    def fake_capture(**kwargs: object) -> Path:
        output_zip = Path(str(kwargs["output_zip"]))
        capture_run_id = next(capture_ids)
        _write_package(
            output_zip,
            capture_run_id=capture_run_id,
            duplicate_count=1 if "Application" in str(kwargs["search_url"]) else 0,
        )
        return output_zip

    monkeypatch.setattr(linkedin_discovery_batch, "linkedin_capture_browser", fake_browser)
    monkeypatch.setattr(linkedin_discovery_batch, "run_capture_in_context", fake_capture)
    monkeypatch.setattr(
        linkedin_discovery_batch,
        "_batch_evidence_dir",
        lambda batch_id: tmp_path / "evidence" / batch_id,
    )

    with _session(factory) as session:
        execute_discovery_batch(
            session,
            batch.id,
            profile_dir=tmp_path / "profile",
        )
        result = get_discovery_batch(session, batch.id)

    assert browser_sessions == 1
    assert result.status == "completed"
    assert result.completed_search_count == 2
    assert result.failed_search_count == 0
    assert result.captured_count == 4
    assert result.verified_count == 4
    assert result.new_posting_count == 3
    assert result.duplicate_count == 1
    assert [search.capture_run_id for search in result.searches] == [
        first_capture,
        second_capture,
    ]
    assert all(search.status == "completed" for search in result.searches)


def test_authentication_failure_stops_remaining_searches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)

    with _session(factory) as session:
        first = _saved_search(session, "LinkedIn IT Support", "IT%20Support")
        second = _saved_search(
            session,
            "LinkedIn Application Support Engineer",
            "Application%20Support%20Engineer",
        )
        batch = create_discovery_batch(
            session,
            DiscoveryBatchCreateRequest(saved_search_ids=[first.id, second.id]),
        )
        schedule_discovery_batch(session, batch.id)

    @contextmanager
    def fake_browser(_profile_dir: Path) -> Iterator[tuple[object, object]]:
        yield object(), object()

    calls = 0

    def fail_authentication(**_kwargs: object) -> Path:
        nonlocal calls
        calls += 1
        raise RuntimeError("LinkedIn authentication_required: LinkedIn authentication is required.")

    monkeypatch.setattr(linkedin_discovery_batch, "linkedin_capture_browser", fake_browser)
    monkeypatch.setattr(
        linkedin_discovery_batch,
        "run_capture_in_context",
        fail_authentication,
    )
    monkeypatch.setattr(
        linkedin_discovery_batch,
        "_batch_evidence_dir",
        lambda batch_id: tmp_path / "evidence" / batch_id,
    )

    with _session(factory) as session:
        execute_discovery_batch(
            session,
            batch.id,
            profile_dir=tmp_path / "profile",
        )
        result = get_discovery_batch(session, batch.id)

    assert calls == 1
    assert result.status == "failed"
    assert result.failed_search_count == 1
    assert result.searches[0].status == "failed"
    assert result.searches[1].status == "skipped"
    assert "shared LinkedIn session" in result.searches[1].error


def test_browser_start_failure_marks_batch_and_searches_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)

    with _session(factory) as session:
        first = _saved_search(session, "LinkedIn IT Support", "IT%20Support")
        second = _saved_search(
            session,
            "LinkedIn Application Support Engineer",
            "Application%20Support%20Engineer",
        )
        batch = create_discovery_batch(
            session,
            DiscoveryBatchCreateRequest(saved_search_ids=[first.id, second.id]),
        )
        schedule_discovery_batch(session, batch.id)

    @contextmanager
    def broken_browser(_profile_dir: Path) -> Iterator[tuple[object, object]]:
        raise RuntimeError("Chromium profile unavailable")
        yield object(), object()

    monkeypatch.setattr(linkedin_discovery_batch, "linkedin_capture_browser", broken_browser)
    monkeypatch.setattr(
        linkedin_discovery_batch,
        "_batch_evidence_dir",
        lambda batch_id: tmp_path / "evidence" / batch_id,
    )

    with _session(factory) as session:
        with pytest.raises(RuntimeError, match="batch runtime failed"):
            execute_discovery_batch(
                session,
                batch.id,
                profile_dir=tmp_path / "profile",
            )
        linkedin_discovery_batch.mark_discovery_batch_background_failure(
            session,
            batch.id,
            RuntimeError("Chromium profile unavailable"),
        )
        result = get_discovery_batch(session, batch.id)

    assert result.status == "failed"
    assert all(search.status == "skipped" for search in result.searches)
    assert all("background failure" in search.error for search in result.searches)
