from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_global_context_exchange_is_exposed_by_main_app(tmp_path: Path) -> None:
    database_path = tmp_path / "global-context-main.db"
    client = TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))

    response = client.get("/api/ai-context/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_type"] == "jolt_ai_exchange_input"
    assert payload["scope"]["section"] == "global_context"
    assert payload["protected_state"]["patchable_namespaces"]
