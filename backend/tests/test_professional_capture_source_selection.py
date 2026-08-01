from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def test_one_source_professional_capture_selects_career_source_first(tmp_path: Path) -> None:
    client = _client(tmp_path)

    created = client.post(
        "/api/professional-intelligence/capture-runs",
        json={
            "options": {
                "max_sources": 1,
                "max_scroll_batches": 1,
                "max_items_per_source": 5,
                "timeout_seconds": 10,
                "stop_on_failure": True,
            }
        },
    )

    assert created.status_code == 200
    payload = created.json()
    assert [source["source_id"] for source in payload["planned_sources"]] == [
        "linkedin-jobs-preferences"
    ]
    assert payload["planned_sources"][0]["category"] == "career"
    assert "career_sources_prioritized_for_small_runs" in payload["safety_constraints"]


def test_bounded_professional_capture_keeps_career_sources_before_profile_sources(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    created = client.post(
        "/api/professional-intelligence/capture-runs",
        json={
            "options": {
                "max_sources": 3,
                "max_scroll_batches": 1,
                "max_items_per_source": 5,
                "timeout_seconds": 10,
                "stop_on_failure": True,
            }
        },
    )

    assert created.status_code == 200
    source_ids = [source["source_id"] for source in created.json()["planned_sources"]]
    assert source_ids[:2] == [
        "linkedin-jobs-preferences",
        "linkedin-jobs-profile-match",
    ]
    assert source_ids[2] == "linkedin-profile"
