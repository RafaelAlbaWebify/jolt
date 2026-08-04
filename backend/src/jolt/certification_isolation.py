from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

CERTIFICATION_DATABASE_MARKER = "jolt-full-cycle-certification"


def validate_certification_runtime_identity(
    identity: dict[str, Any],
) -> Path:
    """Return the isolated SQLite path or refuse an unsafe certification target."""

    database = identity.get("database")
    if not isinstance(database, dict):
        raise RuntimeError(
            "Certification isolation check failed: runtime identity has no database section."
        )

    database_url = str(database.get("database_url") or "").strip()
    database_path_text = str(database.get("database_path") or "").strip()

    if not database_url.lower().startswith("sqlite:"):
        raise RuntimeError("Full-cycle certification requires an isolated SQLite database.")
    if not database_path_text:
        raise RuntimeError("Full-cycle certification requires a file-backed SQLite database.")

    database_path = Path(database_path_text)
    filename = database_path.name.lower()

    if CERTIFICATION_DATABASE_MARKER not in filename:
        raise RuntimeError(
            "Refusing to run full-cycle certification against a non-certification "
            f"database: {database_path}. Use Invoke-JoltFullCycleCertification.ps1."
        )
    if database_path.suffix.lower() != ".db":
        raise RuntimeError("Certification SQLite database must use a disposable .db file.")

    return database_path


def assert_certification_backend(
    api_url: str = "http://127.0.0.1:8000",
) -> Path:
    """Inspect the running backend before any certification fixture is created."""

    endpoint = f"{api_url.rstrip('/')}/api/runtime-identity"
    try:
        with urllib.request.urlopen(endpoint, timeout=10) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Unable to verify certification database isolation through {endpoint}."
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "Certification isolation check failed: runtime identity was not an object."
        )

    return validate_certification_runtime_identity(payload)
