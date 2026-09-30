from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _output(section: str, context_patch: dict[str, object]) -> dict[str, object]:
    return {
        "contract_type": "jolt_ai_exchange_output",
        "contract_version": "1.0",
        "exchange_id": f"exchange-{section}",
        "reviewed_at": "2026-09-30T10:00:00Z",
        "review_source": "chatgpt",
        "review_version": "authority-test-v1",
        "scope": {
            "section": section,
            "analysis_types": ["context_update"],
        },
        "feedback": [],
        "context_patch": context_patch,
        "summary": {},
    }


def test_direct_global_context_import_is_blocked(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    response = client.post(
        "/api/ai-context/import",
        json=_output("global_context", {"capture_strategy": {"source": "legacy"}}),
    )

    assert response.status_code == 409
    assert "unified work package" in response.json()["detail"].lower()


def test_individual_exchange_cannot_patch_durable_context(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    response = client.post(
        "/api/ai-search-preferences/import",
        json=_output("search_preferences", {"capture_strategy": {"source": "legacy"}}),
    )

    assert response.status_code == 400
    assert "unified work package" in response.json()["detail"].lower()


def test_openapi_marks_legacy_ai_paths_deprecated_but_unified_path_current(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/api/ai-work-package/import"]["post"].get("deprecated") is not True
    assert schema["paths"]["/api/ai-search-preferences/import"]["post"]["deprecated"] is True
    assert schema["paths"]["/api/ai-context/import"]["post"]["deprecated"] is True
    assert (
        schema["paths"]["/api/linkedin-discovery-batches/{batch_id}/ai-review-import"]["post"][
            "deprecated"
        ]
        is True
    )
