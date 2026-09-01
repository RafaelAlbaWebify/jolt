from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_review_inbox_exchange_is_exposed_by_main_app(tmp_path: Path) -> None:
    database_path = tmp_path / "jolt.db"
    client = TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))

    response = client.get("/api/exports/review-inbox-ai-exchange")

    assert response.status_code == 404
    assert "No capture run exists" in response.json()["detail"]
