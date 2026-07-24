from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(database_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))


def test_professional_intelligence_source_registry_api(tmp_path: Path) -> None:
    client = _client(tmp_path / "jolt.db")

    response = client.get("/api/professional-intelligence/sources")

    assert response.status_code == 200
    sources = response.json()
    assert len(sources) == 14
    assert sum(source["initial_scope"] for source in sources) == 8
    assert {source["category"] for source in sources} == {"profile", "network", "career"}
    assert {source["capture_mode"] for source in sources} == {"supervised_read_only"}
    assert {source["enabled"] for source in sources} == {True}
    assert all(source["url"].startswith("https://www.linkedin.com/") for source in sources)
    assert {source["source_id"] for source in sources if source["initial_scope"]} == {
        "linkedin-profile",
        "linkedin-experience",
        "linkedin-featured",
        "linkedin-activity-all",
        "linkedin-certifications",
        "linkedin-skills",
        "linkedin-jobs-preferences",
        "linkedin-jobs-profile-match",
    }


def test_source_override_persists_across_restart_and_can_reset(tmp_path: Path) -> None:
    database_path = tmp_path / "overrides.db"
    client = _client(database_path)
    update = client.post(
        "/api/professional-intelligence/sources/linkedin-feed/update",
        json={
            "label": "Curated feed review",
            "url": "https://www.linkedin.com/feed/?source=jolt-review",
            "initial_scope": True,
            "enabled": False,
        },
    )

    assert update.status_code == 200
    assert update.json() == {
        "source_id": "linkedin-feed",
        "label": "Curated feed review",
        "category": "network",
        "url": "https://www.linkedin.com/feed/?source=jolt-review",
        "initial_scope": True,
        "enabled": False,
        "capture_mode": "supervised_read_only",
    }

    restarted = _client(database_path)
    persisted = restarted.get("/api/professional-intelligence/sources").json()
    feed = next(source for source in persisted if source["source_id"] == "linkedin-feed")
    assert feed["label"] == "Curated feed review"
    assert feed["initial_scope"] is True
    assert feed["enabled"] is False

    reset = restarted.post("/api/professional-intelligence/sources/linkedin-feed/reset")
    assert reset.status_code == 200
    assert reset.json()["label"] == "Feed"
    assert reset.json()["url"] == "https://www.linkedin.com/feed/"
    assert reset.json()["initial_scope"] is False
    assert reset.json()["enabled"] is True


def test_source_override_rejects_unapproved_or_duplicate_urls(tmp_path: Path) -> None:
    client = _client(tmp_path / "validation.db")
    invalid = client.post(
        "/api/professional-intelligence/sources/linkedin-feed/update",
        json={
            "label": "Unsafe",
            "url": "https://example.com/feed/",
            "initial_scope": False,
            "enabled": True,
        },
    )
    assert invalid.status_code == 422

    duplicate = client.post(
        "/api/professional-intelligence/sources/linkedin-feed/update",
        json={
            "label": "Duplicate",
            "url": "https://www.linkedin.com/in/rafael-alba-tech/",
            "initial_scope": False,
            "enabled": True,
        },
    )
    assert duplicate.status_code == 409

    unknown = client.post(
        "/api/professional-intelligence/sources/not-confirmed/update",
        json={
            "label": "Unknown",
            "url": "https://www.linkedin.com/in/unknown/",
            "initial_scope": False,
            "enabled": True,
        },
    )
    assert unknown.status_code == 404
