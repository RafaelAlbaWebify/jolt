from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    database = tmp_path / "multisource.db"
    return TestClient(create_app(f"sqlite:///{database.as_posix()}"))


def test_discovery_sources_expose_portal_capabilities(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/discovery-sources")
    assert response.status_code == 200
    sources = {item["source"]: item for item in response.json()}

    assert sources["linkedin"]["execution_available"] is True
    assert sources["linkedin"]["transport"] == "browser"
    assert sources["indeed"]["transport"] == "browser"
    assert sources["indeed"]["execution_available"] is True
    assert sources["jobgether"]["transport"] == "api"
    assert sources["infojobs"]["transport"] == "api"


def test_generic_searches_are_portal_specific_and_independent(tmp_path: Path) -> None:
    client = _client(tmp_path)

    indeed = client.post(
        "/api/discovery-searches",
        json={
            "source": "indeed",
            "label": "Indeed Application Support Spain",
            "definition": {
                "search_url": "https://es.indeed.com/jobs?q=application+support&l=Espa%C3%B1a",
            },
            "notes": "",
            "enabled": True,
            "max_jobs": 50,
        },
    )
    assert indeed.status_code == 200, indeed.text

    jobgether = client.post(
        "/api/discovery-searches",
        json={
            "source": "jobgether",
            "label": "Jobgether Application Support Europe",
            "definition": {
                "keyword": "Application Support",
                "locations": ["europe"],
            },
            "notes": "",
            "enabled": True,
            "max_jobs": 25,
        },
    )
    assert jobgether.status_code == 200, jobgether.text

    listed = client.get("/api/discovery-searches")
    assert listed.status_code == 200
    rows = listed.json()
    assert [(item["source"], item["label"]) for item in rows] == [
        ("indeed", "Indeed Application Support Spain"),
        ("jobgether", "Jobgether Application Support Europe"),
    ]
    assert rows[0]["definition"]["search_url"].startswith("https://es.indeed.com/")
    assert rows[1]["definition"]["locations"] == ["europe"]


def test_unified_discovery_list_includes_existing_linkedin_searches(tmp_path: Path) -> None:
    client = _client(tmp_path)

    linkedin = client.post(
        "/api/linkedin-searches",
        json={
            "label": "LinkedIn IT Operations EU",
            "search_url": (
                "https://www.linkedin.com/jobs/search/?f_TPR=r604800"
                "&f_WT=2&geoId=91000000&keywords=IT%20Operations%20Engineer&sortBy=DD"
            ),
            "notes": "",
            "enabled": True,
            "max_jobs": 50,
            "max_pages": 5,
        },
    )
    assert linkedin.status_code == 200, linkedin.text

    listed = client.get("/api/discovery-searches")
    assert listed.status_code == 200
    row = listed.json()[0]
    assert row["id"] == linkedin.json()["id"]
    assert row["source"] == "linkedin"
    assert row["definition"]["search_url"] == linkedin.json()["search_url"]
    assert row["definition"]["max_pages"] == 5
    assert row["execution_available"] is True


def test_generic_discovery_search_rejects_duplicate_definition_per_portal(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = {
        "source": "jobgether",
        "label": "Support Europe",
        "definition": {"keyword": "support", "locations": ["europe"]},
        "notes": "",
        "enabled": True,
        "max_jobs": 25,
    }

    first = client.post("/api/discovery-searches", json=payload)
    assert first.status_code == 200

    second = client.post(
        "/api/discovery-searches",
        json={**payload, "label": "Same Jobgether query"},
    )
    assert second.status_code == 422
    assert "already uses this portal and search definition" in second.json()["detail"]


def test_linkedin_creation_stays_on_existing_editor_during_migration(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/discovery-searches",
        json={
            "source": "linkedin",
            "label": "Do not duplicate LinkedIn storage",
            "definition": {"search_url": "https://www.linkedin.com/jobs/search/?keywords=support"},
            "enabled": True,
            "max_jobs": 50,
        },
    )
    assert response.status_code == 422
    assert "existing LinkedIn search editor" in response.json()["detail"]
