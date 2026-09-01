from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_main_app_exposes_professional_evidence_exchange(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    exported = client.get("/api/ai-professional-evidence/export")
    assert exported.status_code == 200
    assert exported.json()["scope"]["section"] == "professional_evidence"

    feedback = client.get("/api/ai-professional-evidence/feedback")
    assert feedback.status_code == 200
