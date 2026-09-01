from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_main_app_exposes_unified_ai_work_package(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    exported = client.get("/api/ai-work-package/export")
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["contract_type"] == "jolt_ai_work_package"
    assert len(payload["exchanges"]) == 7
    assert all(exchange["context"] == {} for exchange in payload["exchanges"])

    imported = client.post(
        "/api/ai-work-package/import",
        json={
            "contract_type": "jolt_ai_work_package_update",
            "contract_version": "1.0",
            "package_id": payload["package_id"],
            "source_context_version": payload["context_version"],
            "reviewed_at": "2026-09-01T16:00:00+00:00",
            "review_source": "chatgpt",
            "review_version": "unified-v1",
            "review_inbox": None,
            "exchanges": [],
            "context_patch": {},
            "summary": {"executive_summary": "No-op import contract check."},
        },
    )
    assert imported.status_code == 200
    assert imported.json()["package_id"] == payload["package_id"]
    assert imported.json()["imported_sections"] == []
