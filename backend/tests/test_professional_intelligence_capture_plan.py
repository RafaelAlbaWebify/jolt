from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_capture_plan_previews_enabled_initial_sources_without_execution(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))
    client.post(
        "/api/professional-intelligence/sources/linkedin-skills/update",
        json={
            "label": "Skills",
            "url": "https://www.linkedin.com/in/rafael-alba-tech/details/skills/",
            "initial_scope": True,
            "enabled": False,
        },
    )
    client.post(
        "/api/professional-intelligence/sources/linkedin-feed/update",
        json={
            "label": "Feed",
            "url": "https://www.linkedin.com/feed/",
            "initial_scope": True,
            "enabled": True,
        },
    )

    response = client.get("/api/professional-intelligence/capture-plan")

    assert response.status_code == 200
    plan = response.json()
    assert plan["mode"] == "preview_only"
    assert plan["execution_available"] is False
    planned_ids = {source["source_id"] for source in plan["planned_sources"]}
    assert "linkedin-feed" in planned_ids
    assert "linkedin-skills" not in planned_ids
    exclusions = {item["source"]["source_id"]: item["reason"] for item in plan["excluded_sources"]}
    assert exclusions["linkedin-skills"] == "disabled_by_user"
    assert exclusions["linkedin-connections"] == "deferred_scope"
    assert "explicit_user_start_required" in plan["safety_constraints"]
    assert "no_unattended_capture" in plan["safety_constraints"]
