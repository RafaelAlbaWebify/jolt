from __future__ import annotations

import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _declared_package_version() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def test_api_and_package_versions_stay_in_sync(tmp_path: Path) -> None:
    package_version = _declared_package_version()
    database_path = tmp_path / "version-authority.sqlite3"
    app = create_app(f"sqlite:///{database_path.as_posix()}")

    assert package_version == "0.8.0"
    assert app.version == package_version

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["version"] == package_version
