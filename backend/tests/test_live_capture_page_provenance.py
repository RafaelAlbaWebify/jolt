from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from playwright.sync_api import TimeoutError

from jolt import capture_runtime_enhancements
from jolt.capture_runtime_enhancements import (
    _click_with_one_retry,
    _is_relevant_filter_label,
    _reset_runtime_state,
)
from jolt.main import create_app


def test_live_capture_persists_real_page_provenance(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'pages.db').as_posix()}"))
    response = client.post(
        "/api/captures/linkedin/live",
        json={
            "search_url": "https://www.linkedin.com/jobs/search/?keywords=technical%20support",
            "requested_item_limit": 2,
            "stop_reason": "requested_limit_reached",
            "pages": [
                {
                    "page_number": 1,
                    "visible_job_ids": ["1001", "1002"],
                    "next_control_present": True,
                    "next_control_enabled": True,
                },
                {
                    "page_number": 2,
                    "visible_job_ids": ["1003", "1004"],
                    "next_control_present": True,
                    "next_control_enabled": True,
                },
            ],
            "items": [
                {
                    "source_job_id": "1001",
                    "source_url": "https://www.linkedin.com/jobs/view/1001",
                    "title": "Technical Support Engineer",
                    "company": "Example One",
                    "location": "Remote Europe",
                    "description": "Technical support, incidents, APIs and integrations.",
                    "identity_verified": True,
                },
                {
                    "source_job_id": "1003",
                    "source_url": "https://www.linkedin.com/jobs/view/1003",
                    "title": "Application Support Engineer",
                    "company": "Example Two",
                    "location": "Spain",
                    "description": "Application support, SQL and production incidents.",
                    "identity_verified": True,
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["search_url"].endswith("keywords=technical%20support")
    assert [page["page_number"] for page in payload["pages"]] == [1, 2]
    assert payload["pages"][0]["visible_job_ids"] == ["1001", "1002"]
    assert payload["pages"][1]["visible_job_ids"] == ["1003", "1004"]

    capture_id = payload["capture_run_id"]
    stored = client.get(f"/api/captures/{capture_id}")
    assert stored.status_code == 200
    assert stored.json()["pages"] == payload["pages"]


def test_click_retries_once_before_succeeding(monkeypatch) -> None:
    _reset_runtime_state()
    attempts = 0

    class FakeLink:
        def click(self, *, timeout: int) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TimeoutError("first click timed out")

    class FakeCard:
        def scroll_into_view_if_needed(self, *, timeout: int) -> None:
            return None

    link = FakeLink()
    monkeypatch.setattr(
        "jolt.capture_runtime_enhancements.multipage_capture._title_link",
        lambda _: link,
    )

    assert _click_with_one_retry(link, FakeCard()) is True  # type: ignore[arg-type]
    assert attempts == 2
    assert capture_runtime_enhancements._retry_metrics == {
        "retry_attempted_count": 1,
        "recovered_after_retry_count": 1,
        "failed_after_retry_count": 0,
    }


def test_runtime_state_reset_clears_retry_metrics() -> None:
    _reset_runtime_state()
    capture_runtime_enhancements._retry_metrics["retry_attempted_count"] = 4
    capture_runtime_enhancements._retry_metrics["recovered_after_retry_count"] = 2
    capture_runtime_enhancements._retry_metrics["failed_after_retry_count"] = 2

    _reset_runtime_state()

    assert capture_runtime_enhancements._retry_metrics == {
        "retry_attempted_count": 0,
        "recovered_after_retry_count": 0,
        "failed_after_retry_count": 0,
    }


def test_unrelated_following_control_is_not_a_job_filter() -> None:
    assert _is_relevant_filter_label("Following") is False
    assert _is_relevant_filter_label("  Following  ") is False
    assert _is_relevant_filter_label("Remote") is True
    assert _is_relevant_filter_label("Past week") is True
