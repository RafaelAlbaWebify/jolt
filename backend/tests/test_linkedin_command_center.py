from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def test_linkedin_command_center_tracks_capture_changes(tmp_path: Path) -> None:
    client = _client(tmp_path)

    first = client.post(
        "/api/linkedin-command-center/captures",
        json={
            "category": "profile",
            "title": "Profile baseline",
            "source_url": "https://www.linkedin.com/in/example/",
            "visible_text": "Headline A\nAbout A",
            "notes": "User-approved profile snapshot.",
        },
    )
    assert first.status_code == 200
    first_capture = first.json()
    assert first_capture["changed_since_previous"] is False
    assert first_capture["previous_capture_id"] is None

    second = client.post(
        "/api/linkedin-command-center/captures",
        json={
            "category": "profile",
            "title": "Profile after headline update",
            "source_url": "https://www.linkedin.com/in/example/",
            "visible_text": "Headline B\nAbout A",
        },
    )
    assert second.status_code == 200
    second_capture = second.json()
    assert second_capture["changed_since_previous"] is True
    assert second_capture["previous_capture_id"] == first_capture["id"]

    dashboard = client.get("/api/linkedin-command-center")
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["capture_count"] == 2
    assert payload["categories"] == {"profile": 2}


def test_linkedin_command_center_recommendations_and_export(tmp_path: Path) -> None:
    client = _client(tmp_path)
    capture = client.post(
        "/api/linkedin-command-center/captures",
        json={
            "category": "activity",
            "title": "Recent activity",
            "visible_text": "Commented on application support troubleshooting.",
        },
    ).json()

    created = client.post(
        "/api/linkedin-command-center/recommendations",
        json={
            "capture_id": capture["id"],
            "recommendation_type": "content_action",
            "target_area": "activity",
            "title": "Publish support troubleshooting post",
            "rationale": "Reinforces target application support positioning.",
            "proposed_action": "Draft one short post from a real incident pattern.",
            "priority": "high",
        },
    )
    assert created.status_code == 200
    recommendation = created.json()
    assert recommendation["status"] == "pending"

    updated = client.post(
        f"/api/linkedin-command-center/recommendations/{recommendation['id']}/status",
        json={"status": "accepted"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "accepted"

    exported = client.get("/api/linkedin-command-center/export")
    assert exported.status_code == 200
    archive_path = tmp_path / "linkedin.zip"
    archive_path.write_bytes(exported.content)
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert "prompt.md" in names
        assert "data/linkedin_command_center.json" in names
        assert "data/linkedin_recommendations.csv" in names
        dataset = archive.read("data/linkedin_command_center.json").decode("utf-8")
        assert "Publish support troubleshooting post" in dataset
        assert "Do not automate LinkedIn actions" in dataset
