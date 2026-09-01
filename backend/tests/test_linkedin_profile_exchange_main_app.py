from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_main_app_exposes_linkedin_profile_exchange(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    exported = client.get("/api/ai-linkedin/export")
    assert exported.status_code == 200
    assert exported.json()["scope"]["section"] == "linkedin_profile"

    feedback = client.get("/api/ai-linkedin/feedback")
    assert feedback.status_code == 200
