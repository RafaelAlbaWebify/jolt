from pathlib import Path

from fastapi.testclient import TestClient

from jolt.database import create_session_factory
from jolt.main import create_app
from jolt.professional_intelligence_capture_runs import AUTHORIZATION_CONFIRMATION_PHRASE
from jolt.professional_intelligence_supervised_capture import (
    CapturedProfessionalPage,
    start_professional_supervised_capture,
)


def create_authorized_capture_run(
    client: TestClient, *, stop_on_failure: bool
) -> dict[str, object]:
    created = client.post(
        "/api/professional-intelligence/capture-runs",
        json={
            "options": {
                "max_sources": 3,
                "max_scroll_batches": 1,
                "max_items_per_source": 10,
                "timeout_seconds": 20,
                "stop_on_failure": stop_on_failure,
            }
        },
    ).json()
    assert len(created["planned_sources"]) >= 3
    authorized = client.post(
        f"/api/professional-intelligence/capture-runs/{created['id']}/authorize",
        json={"confirmation_phrase": AUTHORIZATION_CONFIRMATION_PHRASE, "user_present": True},
    )
    assert authorized.status_code == 200
    client.get("/api/professional-intelligence/evidence-root")
    return created


def fixture_capture_source_that_fails_second(calls: list[str]):
    def capture(url: str) -> CapturedProfessionalPage:
        calls.append(url)
        if len(calls) == 2:
            raise RuntimeError("fixture source failure")
        return CapturedProfessionalPage(
            screenshot_png=b"png",
            visible_text="visible professional evidence " * 8,
            title="Fixture capture",
            final_url=url,
            http_status=200,
        )

    return capture


def test_stop_on_failure_skips_remaining_sources_after_first_failed_source(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))
    created = create_authorized_capture_run(client, stop_on_failure=True)
    planned_source_ids = [source["source_id"] for source in created["planned_sources"]]
    calls: list[str] = []

    session = create_session_factory(database_url)()
    try:
        completed = start_professional_supervised_capture(
            session,
            str(created["id"]),
            capture_source=fixture_capture_source_that_fails_second(calls),
        )
    finally:
        session.close()

    assert len(calls) == 2
    assert completed.status == "completed_with_gaps"
    assert completed.stop_reason == "stopped_after_first_source_failure"
    progress = {item.source_id: item for item in completed.source_progress}
    assert progress[planned_source_ids[0]].status == "completed"
    assert progress[planned_source_ids[1]].status == "failed"
    assert progress[planned_source_ids[2]].status == "skipped"
    assert "stop_on_failure" in progress[planned_source_ids[2]].detail


def test_stop_on_failure_false_continues_after_failed_source(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))
    created = create_authorized_capture_run(client, stop_on_failure=False)
    planned_source_ids = [source["source_id"] for source in created["planned_sources"]]
    calls: list[str] = []

    session = create_session_factory(database_url)()
    try:
        completed = start_professional_supervised_capture(
            session,
            str(created["id"]),
            capture_source=fixture_capture_source_that_fails_second(calls),
        )
    finally:
        session.close()

    assert len(calls) == 3
    assert completed.status == "completed_with_gaps"
    assert completed.stop_reason == "one_or_more_sources_partial_or_failed"
    progress = {item.source_id: item for item in completed.source_progress}
    assert progress[planned_source_ids[0]].status == "completed"
    assert progress[planned_source_ids[1]].status == "failed"
    assert progress[planned_source_ids[2]].status == "completed"
