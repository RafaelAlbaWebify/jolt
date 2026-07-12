from fastapi.testclient import TestClient

from jolt.main import create_app


def test_health_endpoint_and_local_cors(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'health.db').as_posix()}"
    client = TestClient(create_app(database_url))

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "jolt-backend",
        "version": "0.5.0",
    }

    preflight = client.options(
        "/api/opportunities",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
