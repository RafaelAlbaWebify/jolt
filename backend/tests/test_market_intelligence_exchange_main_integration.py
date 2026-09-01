from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_market_exchange_is_exposed_by_main_app(tmp_path: Path) -> None:
    database_path = tmp_path / "jolt.db"
    client = TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))

    response = client.get("/api/ai-market/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["section"] == "market_insights"
    assert payload["evidence"]["counts"] == {"jobs": 0, "capture_runs": 0}
