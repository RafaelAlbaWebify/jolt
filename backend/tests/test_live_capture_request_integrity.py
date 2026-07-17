from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jolt.main import create_app


def _payload() -> dict[str, object]:
    return {
        "search_url": "https://www.linkedin.com/jobs/search/?keywords=support",
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
                "visible_job_ids": ["1003"],
                "next_control_present": False,
                "next_control_enabled": False,
            },
        ],
        "items": [
            {
                "source_job_id": "1001",
                "source_url": "https://www.linkedin.com/jobs/view/1001",
                "identity_verified": False,
                "verification_reason": "synthetic request-boundary test",
            },
            {
                "source_job_id": "1003",
                "source_url": "https://www.linkedin.com/jobs/view/1003",
                "identity_verified": False,
                "verification_reason": "synthetic request-boundary test",
            },
        ],
    }


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'integrity.db').as_posix()}"))


def _assert_unprocessable(client: TestClient, payload: dict[str, object]) -> None:
    response = client.post("/api/captures/linkedin/live", json=payload)
    assert response.status_code == 422, response.text


def test_valid_page_evidence_is_accepted_and_normalized(client: TestClient) -> None:
    payload = _payload()
    pages = payload["pages"]
    assert isinstance(pages, list)
    pages[0]["visible_job_ids"] = [" 1001 ", "1002"]

    response = client.post("/api/captures/linkedin/live", json=payload)

    assert response.status_code == 200, response.text
    assert response.json()["pages"][0]["visible_job_ids"] == ["1001", "1002"]


def test_duplicate_page_numbers_return_422(client: TestClient) -> None:
    payload = _payload()
    pages = payload["pages"]
    assert isinstance(pages, list)
    pages[1]["page_number"] = 1
    _assert_unprocessable(client, payload)


def test_non_contiguous_page_numbers_return_422(client: TestClient) -> None:
    payload = _payload()
    pages = payload["pages"]
    assert isinstance(pages, list)
    pages[1]["page_number"] = 3
    _assert_unprocessable(client, payload)


def test_enabled_next_control_requires_present_control(client: TestClient) -> None:
    payload = _payload()
    pages = payload["pages"]
    assert isinstance(pages, list)
    pages[0]["next_control_present"] = False
    pages[0]["next_control_enabled"] = True
    _assert_unprocessable(client, payload)


def test_duplicate_item_job_ids_return_422(client: TestClient) -> None:
    payload = _payload()
    items = payload["items"]
    assert isinstance(items, list)
    duplicate = deepcopy(items[0])
    duplicate["source_job_id"] = " 1001 "
    items.append(duplicate)
    _assert_unprocessable(client, payload)


def test_submitted_item_missing_from_page_evidence_returns_422(client: TestClient) -> None:
    payload = _payload()
    items = payload["items"]
    assert isinstance(items, list)
    items[1]["source_job_id"] = "9999"
    _assert_unprocessable(client, payload)


@pytest.mark.parametrize("visible_job_ids", [[""], ["   "], ["1001", " 1001 "]])
def test_invalid_visible_job_ids_return_422(
    client: TestClient,
    visible_job_ids: list[str],
) -> None:
    payload = _payload()
    pages = payload["pages"]
    assert isinstance(pages, list)
    pages[0]["visible_job_ids"] = visible_job_ids
    _assert_unprocessable(client, payload)
