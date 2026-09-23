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
