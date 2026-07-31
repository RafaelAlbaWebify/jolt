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
        assert "/api/linkedin-command-center/recommendations/import" in dataset


def test_linkedin_command_center_imports_chatgpt_recommendations(tmp_path: Path) -> None:
    client = _client(tmp_path)

    imported = client.post(
        "/api/linkedin-command-center/recommendations/import",
        json={
            "source": "chatgpt_package",
            "recommendations": [
                {
                    "recommendation_type": "profile_update",
                    "target_area": "headline",
                    "title": "Clarify Application Support positioning",
                    "rationale": "The captured profile does not make the target role obvious.",
                    "proposed_action": "Rewrite the headline manually in LinkedIn.",
                    "proposed_text": "Application Support Engineer | IT Operations | SQL, Windows, M365",
                    "priority": "high",
                },
                {
                    "recommendation_type": "network_decision",
                    "target_area": "target recruiters",
                    "title": "Prioritize relevant recruiters",
                    "rationale": "Focus on recruiters hiring for support roles rather than noisy contacts.",
                    "proposed_action": "Review and manually connect with selected recruiters.",
                    "priority": "medium",
                },
            ],
        },
    )
    assert imported.status_code == 200
    payload = imported.json()
    assert payload["imported_count"] == 2

    dashboard = client.get("/api/linkedin-command-center").json()
    assert dashboard["recommendation_count"] == 2
    assert dashboard["recommendation_types"]["profile_update"] == 1
    assert dashboard["recommendation_types"]["network_decision"] == 1
    assert {item["status"] for item in dashboard["recommendations"]} == {"pending"}


def test_linkedin_playwright_capture_endpoint_uses_service(tmp_path: Path, monkeypatch) -> None:
    from jolt import main as main_module

    def fake_capture(session, request):
        return main_module.create_linkedin_capture(
            session,
            main_module.LinkedInCaptureRequest(
                category=request.category,
                title=request.title,
                source_url=request.url,
                visible_text="captured visible LinkedIn text",
                notes="Browser session kept open for multi-section captures.",
            ),
        )

    monkeypatch.setattr(main_module, "run_linkedin_playwright_capture", fake_capture)
    client = _client(tmp_path)

    captured = client.post(
        "/api/linkedin-command-center/captures/playwright",
        json={"category": "profile", "title": "Profile", "url": "https://www.linkedin.com/in/example/"},
    )

    assert captured.status_code == 200
    payload = captured.json()
    assert payload["title"] == "Profile"
    assert payload["source_url"] == "https://www.linkedin.com/in/example/"
    assert "multi-section" in payload["notes"]
