from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app
from jolt.professional_intelligence_evidence_root import resolve_professional_evidence_path


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def test_evidence_root_configures_persists_and_clears(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    client = TestClient(create_app(database_url))

    initial = client.get("/api/professional-intelligence/evidence-root")
    assert initial.status_code == 200
    assert initial.json() == {
        "configured": False,
        "root_path": None,
        "exists": False,
        "writable": False,
        "verified_at": None,
    }

    configured = client.post(
        "/api/professional-intelligence/evidence-root",
        json={"root_path": str(evidence_root)},
    )
    assert configured.status_code == 200
    payload = configured.json()
    assert payload["configured"] is True
    assert payload["root_path"] == str(evidence_root.resolve())
    assert payload["exists"] is True
    assert payload["writable"] is True
    assert payload["verified_at"] is not None

    restarted = TestClient(create_app(database_url))
    persisted = restarted.get("/api/professional-intelligence/evidence-root")
    assert persisted.status_code == 200
    assert persisted.json()["root_path"] == str(evidence_root.resolve())

    cleared = restarted.delete("/api/professional-intelligence/evidence-root")
    assert cleared.status_code == 200
    assert cleared.json()["configured"] is False


def test_evidence_root_rejects_missing_or_non_directory_path(tmp_path: Path) -> None:
    client = _client(tmp_path)
    missing = client.post(
        "/api/professional-intelligence/evidence-root",
        json={"root_path": str(tmp_path / "missing")},
    )
    assert missing.status_code == 422

    file_path = tmp_path / "file.txt"
    file_path.write_text("not a directory", encoding="utf-8")
    file_response = client.post(
        "/api/professional-intelligence/evidence-root",
        json={"root_path": str(file_path)},
    )
    assert file_response.status_code == 422


def test_evidence_path_resolution_remains_contained(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    root.mkdir()

    resolved = resolve_professional_evidence_path(
        str(root), "run-1", "linkedin-profile", "page.png"
    )
    assert resolved == root.resolve() / "run-1" / "linkedin-profile" / "page.png"

    for unsafe in ("../outside", "nested/path", ""):
        try:
            resolve_professional_evidence_path(str(root), unsafe, "linkedin-profile", "page.png")
        except ValueError:
            pass
        else:
            raise AssertionError(f"Unsafe component was accepted: {unsafe!r}")
