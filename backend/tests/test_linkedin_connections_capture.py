from __future__ import annotations

from typing import Any, cast

import pytest

from jolt import linkedin_playwright_capture as capture_module
from jolt.linkedin_playwright_capture import (
    _canonical_profile_url,
    _collect_connections,
    _is_connections_url,
    _normalize_connection_record,
    _serialize_connections_payload,
)


def test_connections_url_is_detected() -> None:
    assert _is_connections_url("https://www.linkedin.com/mynetwork/invite-connect/connections/")
    assert not _is_connections_url("https://www.linkedin.com/in/example/")


def test_profile_url_is_canonicalized() -> None:
    assert (
        _canonical_profile_url(
            "https://www.linkedin.com/in/example-person/?miniProfileUrn=abc#details"
        )
        == "https://www.linkedin.com/in/example-person/"
    )


def test_connection_record_requires_a_name() -> None:
    assert (
        _normalize_connection_record(
            {
                "name": "",
                "profile_url": "https://www.linkedin.com/in/example/",
            },
            1,
        )
        is None
    )


def test_connection_record_preserves_visible_fields() -> None:
    record = _normalize_connection_record(
        {
            "name": "Example Person",
            "profile_url": "https://www.linkedin.com/in/example/?tracking=1",
            "headline": "Technical Recruiter",
            "connection_context": "1st degree connection",
        },
        3,
    )

    assert record == {
        "name": "Example Person",
        "profile_url": "https://www.linkedin.com/in/example/",
        "headline": "Technical Recruiter",
        "connection_context": "1st degree connection",
        "capture_order": 3,
    }


def _playwright_page(markup: str) -> tuple[Any, Any, Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    playwright = sync_api.sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content(markup)
    return playwright, browser, page


def test_bounded_playwright_fixture_collects_unique_connections_from_scroll_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(capture_module, "_SCROLL_WAIT_MILLISECONDS", 0)
    playwright, browser, page = _playwright_page(
        """
        <style>
          #connections { height: 100px; overflow-y: auto; display: block; }
          #connections li { height: 70px; display: block; }
        </style>
        <ul id="connections">
          <li><a href="https://www.linkedin.com/in/alpha/">Alpha Person</a><span>Engineer</span></li>
          <li><a href="https://www.linkedin.com/in/beta/">Beta Person</a><span>Recruiter</span></li>
          <li aria-hidden="true" style="height: 600px"></li>
        </ul>
        <script>
          let loaded = false;
          document.querySelector("#connections").addEventListener("scroll", () => {
            if (loaded) return;
            const row = document.createElement("li");
            row.innerHTML =
              '<a href="https://www.linkedin.com/in/gamma/?trk=test">Gamma Person</a>' +
              '<span>Support Manager</span>';
            document.querySelector("#connections").appendChild(row);
            loaded = true;
          });
        </script>
        """
    )
    try:
        payload = _collect_connections(page, 3)
    finally:
        browser.close()
        playwright.stop()

    run = cast(dict[str, Any], payload["capture_run"])
    connections = cast(list[dict[str, Any]], payload["connections"])

    assert run["requested_limit"] == 3
    assert run["unique_count"] == 3
    assert run["scroll_count"] >= 1
    assert run["stop_reason"] == "requested_limit_reached"
    assert run["status"] == "complete"
    assert "scrollable_container" in run["scroll_strategies"]
    assert [item["name"] for item in connections] == [
        "Alpha Person",
        "Beta Person",
        "Gamma Person",
    ]
    assert connections[2]["profile_url"] == "https://www.linkedin.com/in/gamma/"
    assert all(item["captured_at"] for item in connections)
    assert all("source_url" in item for item in connections)


def test_playwright_fixture_stops_on_linkedin_safety_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(capture_module, "_SCROLL_WAIT_MILLISECONDS", 0)
    playwright, browser, page = _playwright_page(
        """
        <ul>
          <li><a href="https://www.linkedin.com/in/alpha/">Alpha Person</a></li>
        </ul>
        <p>We detected automated activity on your account</p>
        """
    )
    try:
        payload = _collect_connections(page, 5)
    finally:
        browser.close()
        playwright.stop()

    run = cast(dict[str, Any], payload["capture_run"])
    assert run["unique_count"] == 0
    assert run["stop_reason"] == "linkedin_safety_warning"
    assert run["status"] == "partial"
    assert run["failures"] == ["LinkedIn safety warning detected: we detected automated activity."]


def test_stagnant_scrolls_remain_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_module, "_SCROLL_WAIT_MILLISECONDS", 0)
    playwright, browser, page = _playwright_page(
        '<ul><li><a href="https://www.linkedin.com/in/alpha/">Alpha Person</a></li></ul>'
    )
    try:
        payload = _collect_connections(page, 5)
    finally:
        browser.close()
        playwright.stop()

    run = cast(dict[str, Any], payload["capture_run"])
    assert run["stop_reason"] == "no_new_connections_after_scroll"
    assert run["status"] == "partial"
    assert run["unique_count"] == 1


def test_requested_limit_is_the_only_complete_connections_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(capture_module, "_SCROLL_WAIT_MILLISECONDS", 0)
    playwright, browser, page = _playwright_page(
        '<ul><li><a href="https://www.linkedin.com/in/alpha/">Alpha Person</a></li></ul>'
    )
    try:
        payload = _collect_connections(page, 1)
    finally:
        browser.close()
        playwright.stop()

    run = cast(dict[str, Any], payload["capture_run"])
    assert run["stop_reason"] == "requested_limit_reached"
    assert run["status"] == "complete"
    assert run["unique_count"] == 1


def test_capture_payload_limit_is_reported_as_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(capture_module, "_MAX_CAPTURE_TEXT_CHARACTERS", 400)
    payload: dict[str, object] = {
        "schema": "jolt_linkedin_connections_v1",
        "capture_run": {
            "requested_limit": 2,
            "unique_count": 2,
            "status": "complete",
            "stop_reason": "requested_limit_reached",
            "failures": [],
        },
        "connections": [
            {"name": "A", "headline": "x" * 300},
            {"name": "B", "headline": "y" * 300},
        ],
    }

    serialized = _serialize_connections_payload(payload)
    run = cast(dict[str, Any], payload["capture_run"])

    assert len(serialized) <= 400
    assert run["stop_reason"] == "capture_payload_limit_reached"
    assert run["status"] == "partial"
    assert run["unique_count"] < 2
    assert run["failures"]
