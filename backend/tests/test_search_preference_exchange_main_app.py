from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_main_app_exposes_search_preference_exchange(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    exported = client.get("/api/ai-search-preferences/export")
    assert exported.status_code == 200
    assert exported.json()["scope"]["section"] == "search_preferences"

    feedback = client.get("/api/ai-search-preferences/feedback")
    assert feedback.status_code == 200
