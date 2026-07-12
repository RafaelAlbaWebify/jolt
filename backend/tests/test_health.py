from fastapi.testclient import TestClient

from jolt.main import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "jolt-backend",
        "version": "0.1.0",
    }
