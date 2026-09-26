from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    database = tmp_path / "portfolio.db"
    return TestClient(create_app(f"sqlite:///{database.as_posix()}"))


def _search_payload(
    *,
    label: str = "LinkedIn IT Support",
    keywords: str = "IT%20Support",
    start: str = "",
) -> dict[str, object]:
    pagination = f"&start={start}" if start else ""
    return {
        "label": label,
        "search_url": (
            "https://www.linkedin.com/jobs/search/?currentJobId=4469309319"
            "&f_TPR=r604800&f_WT=2&geoId=91000000"
            f"&keywords={keywords}"
            "&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=true&sortBy=DD"
            f"{pagination}"
        ),
        "notes": "EU remote support search",
        "enabled": True,
        "max_jobs": 100,
        "max_pages": 10,
    }


def test_saved_search_create_normalizes_pagination_and_persists(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/linkedin-searches",
        json=_search_payload(start="50"),
    )
    assert response.status_code == 200, response.text
    saved = response.json()

    assert saved["label"] == "LinkedIn IT Support"
    assert saved["search_url"] == (
        "https://www.linkedin.com/jobs/search/?f_TPR=r604800&f_WT=2"
        "&geoId=91000000&keywords=IT+Support&sortBy=DD"
    )
    assert saved["max_jobs"] == 100
    assert saved["max_pages"] == 10

    listed = client.get("/api/linkedin-searches")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [saved["id"]]


def test_saved_search_rejects_duplicate_canonical_search(tmp_path: Path) -> None:
    client = _client(tmp_path)

    first = client.post("/api/linkedin-searches", json=_search_payload())
    assert first.status_code == 200

    second = client.post(
        "/api/linkedin-searches",
        json=_search_payload(label="Same search from page 3", start="50"),
    )
    assert second.status_code == 422
    assert "already uses these search criteria" in second.json()["detail"]


def test_saved_search_update_preserves_identity_and_changes_label(tmp_path: Path) -> None:
    client = _client(tmp_path)

    created = client.post("/api/linkedin-searches", json=_search_payload()).json()
    updated_payload = _search_payload(label="Primary EU IT Support")
    updated_payload["notes"] = "Weekly remote EU search"

    updated = client.post(
        f"/api/linkedin-searches/{created['id']}",
        json=updated_payload,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["label"] == "Primary EU IT Support"
    assert updated.json()["notes"] == "Weekly remote EU search"
    assert updated.json()["search_url"] == created["search_url"]


def test_discovery_batch_snapshots_selected_searches_in_order(tmp_path: Path) -> None:
    client = _client(tmp_path)

    first = client.post("/api/linkedin-searches", json=_search_payload()).json()
    second = client.post(
        "/api/linkedin-searches",
        json=_search_payload(
            label="LinkedIn Application Support Engineer",
            keywords="Application%20Support%20Engineer",
        ),
    ).json()

    response = client.post(
        "/api/linkedin-discovery-batches",
        json={"saved_search_ids": [second["id"], first["id"]]},
    )
    assert response.status_code == 200, response.text
    batch = response.json()

    assert batch["status"] == "queued"
    assert batch["selected_search_count"] == 2
    assert [item["position"] for item in batch["searches"]] == [1, 2]
    assert [item["saved_search_id"] for item in batch["searches"]] == [
        second["id"],
        first["id"],
    ]
    assert [item["label"] for item in batch["searches"]] == [
        "LinkedIn Application Support Engineer",
        "LinkedIn IT Support",
    ]
    assert all(item["status"] == "queued" for item in batch["searches"])


def test_discovery_history_blocks_delete_but_allows_disable(tmp_path: Path) -> None:
    client = _client(tmp_path)

    created = client.post("/api/linkedin-searches", json=_search_payload()).json()
    batch = client.post(
        "/api/linkedin-discovery-batches",
        json={"saved_search_ids": [created["id"]]},
    )
    assert batch.status_code == 200

    deleted = client.post(f"/api/linkedin-searches/{created['id']}/delete")
    assert deleted.status_code == 409
    assert "discovery history" in deleted.json()["detail"]

    disabled_payload = _search_payload()
    disabled_payload["enabled"] = False
    disabled = client.post(
        f"/api/linkedin-searches/{created['id']}",
        json=disabled_payload,
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


def test_disabled_search_cannot_be_queued_for_discovery(tmp_path: Path) -> None:
    client = _client(tmp_path)

    payload = _search_payload()
    payload["enabled"] = False
    created = client.post("/api/linkedin-searches", json=payload).json()

    response = client.post(
        "/api/linkedin-discovery-batches",
        json={"saved_search_ids": [created["id"]]},
    )
    assert response.status_code == 409
    assert "disabled" in response.json()["detail"]


def test_discovery_batch_start_schedules_once(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    created = client.post("/api/linkedin-searches", json=_search_payload()).json()
    batch = client.post(
        "/api/linkedin-discovery-batches",
        json={"saved_search_ids": [created["id"]]},
    ).json()

    calls: list[str] = []

    def fake_background(_get_session, batch_id: str) -> None:
        calls.append(batch_id)

    from jolt import linkedin_search_portfolio_api

    monkeypatch.setattr(
        linkedin_search_portfolio_api,
        "_run_discovery_batch_background",
        fake_background,
    )

    started = client.post(f"/api/linkedin-discovery-batches/{batch['id']}/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "scheduled"
    assert calls == [batch["id"]]

    repeated = client.post(f"/api/linkedin-discovery-batches/{batch['id']}/start")
    assert repeated.status_code == 409
    assert "Only queued" in repeated.json()["detail"]


def test_only_one_discovery_batch_can_be_active(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    first = client.post("/api/linkedin-searches", json=_search_payload()).json()
    second = client.post(
        "/api/linkedin-searches",
        json=_search_payload(
            label="LinkedIn Application Support Engineer",
            keywords="Application%20Support%20Engineer",
        ),
    ).json()

    batch_one = client.post(
        "/api/linkedin-discovery-batches",
        json={"saved_search_ids": [first["id"]]},
    ).json()
    batch_two = client.post(
        "/api/linkedin-discovery-batches",
        json={"saved_search_ids": [second["id"]]},
    ).json()

    from jolt import linkedin_search_portfolio_api

    monkeypatch.setattr(
        linkedin_search_portfolio_api,
        "_run_discovery_batch_background",
        lambda _get_session, _batch_id: None,
    )

    first_start = client.post(f"/api/linkedin-discovery-batches/{batch_one['id']}/start")
    assert first_start.status_code == 200

    second_start = client.post(f"/api/linkedin-discovery-batches/{batch_two['id']}/start")
    assert second_start.status_code == 409
    assert "already active" in second_start.json()["detail"]


def test_backend_restart_recovers_stale_active_discovery_batch(tmp_path: Path) -> None:
    database = tmp_path / "restart-recovery.db"
    database_url = f"sqlite:///{database.as_posix()}"
    client = TestClient(create_app(database_url))

    search = client.post(
        "/api/linkedin-searches",
        json=_search_payload(),
    ).json()
    batch = client.post(
        "/api/linkedin-discovery-batches",
        json={"saved_search_ids": [search["id"]]},
    ).json()

    # Simulate the exact interrupted UI state: the batch row was created,
    # but Windows/backend stopped before /start could schedule its worker.
    assert batch["status"] == "queued"

    restarted = TestClient(create_app(database_url))
    recovered = restarted.get(
        f"/api/linkedin-discovery-batches/{batch['id']}"
    )

    assert recovered.status_code == 200
    payload = recovered.json()
    assert payload["status"] == "failed"
    assert payload["searches"][0]["status"] == "skipped"
    assert "interrupted" in payload["searches"][0]["error"].lower()

    next_batch = restarted.post(
        "/api/linkedin-discovery-batches",
        json={"saved_search_ids": [search["id"]]},
    )
    assert next_batch.status_code == 200
