from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_main_app_exposes_data_quality_exchange(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    exported = client.get("/api/ai-data-quality/export")
    assert exported.status_code == 200
    assert exported.json()["scope"]["section"] == "data_quality"

    feedback = client.get("/api/ai-data-quality/feedback")
    assert feedback.status_code == 200
