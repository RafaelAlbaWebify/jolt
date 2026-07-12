from fastapi.testclient import TestClient
from jolt.main import create_app


def test_health_endpoint(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'health.db').as_posix()}"
    client = TestClient(create_app(database_url))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "jolt-backend",
        "version": "0.2.0",
    }
