from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_professional_intelligence_source_registry_api(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    response = client.get("/api/professional-intelligence/sources")

    assert response.status_code == 200
    sources = response.json()
    assert len(sources) == 14
    assert sum(source["initial_scope"] for source in sources) == 8
    assert {source["category"] for source in sources} == {"profile", "network", "career"}
    assert {source["capture_mode"] for source in sources} == {"supervised_read_only"}
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
