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


def test_live_capture_accepts_100_job_evidence_batch(client: TestClient) -> None:
    job_ids = [str(900000 + index) for index in range(100)]
    pages = []

    for page_index in range(10):
        start = page_index * 10
        page_ids = job_ids[start : start + 10]
        pages.append(
            {
                "page_number": page_index + 1,
                "visible_job_ids": page_ids,
                "next_control_present": page_index < 9,
                "next_control_enabled": page_index < 9,
            }
        )

    payload = {
        "search_url": "https://www.linkedin.com/jobs/search/?keywords=support",
        "requested_item_limit": 100,
        "stop_reason": "requested_limit_reached",
        "pages": pages,
        "items": [
            {
                "source_job_id": job_id,
                "source_url": f"https://www.linkedin.com/jobs/view/{job_id}",
                "identity_verified": False,
                "verification_reason": "synthetic 100-job capacity test",
            }
            for job_id in job_ids
        ],
    }

    response = client.post("/api/captures/linkedin/live", json=payload)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["requested_item_limit"] == 100
    assert result["observed_item_count"] == 100
    assert result["total_items"] == 100


def test_live_capture_rejects_101_items(client: TestClient) -> None:
    job_ids = [str(910000 + index) for index in range(101)]

    payload = {
        "search_url": "https://www.linkedin.com/jobs/search/",
        "requested_item_limit": 100,
        "items": [
            {
                "source_job_id": job_id,
                "source_url": f"https://www.linkedin.com/jobs/view/{job_id}",
                "identity_verified": False,
                "verification_reason": "synthetic upper-bound test",
            }
            for job_id in job_ids
        ],
    }

    response = client.post("/api/captures/linkedin/live", json=payload)
    assert response.status_code == 422
