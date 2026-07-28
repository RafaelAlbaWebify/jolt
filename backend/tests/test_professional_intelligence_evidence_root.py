from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from fastapi.testclient import TestClient

from jolt.main import create_app
from jolt.professional_intelligence_evidence_root import resolve_professional_evidence_path


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def test_evidence_root_is_provisioned_persists_and_accepts_custom_path(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    initial = client.get("/api/professional-intelligence/evidence-root")
    assert initial.status_code == 200
    initial_payload = initial.json()
    default_root = tmp_path / "professional-evidence"
    assert initial_payload["configured"] is True
    assert initial_payload["root_path"] == str(default_root.resolve())
    assert initial_payload["exists"] is True
    assert initial_payload["writable"] is True
    assert initial_payload["verified_at"] is not None
    assert default_root.is_dir()

    custom_root = tmp_path / "custom" / "evidence"
    configured = client.post(
        "/api/professional-intelligence/evidence-root",
        json={"root_path": str(custom_root)},
    )
    assert configured.status_code == 200
    payload = configured.json()
    assert payload["configured"] is True
    assert payload["root_path"] == str(custom_root.resolve())
    assert payload["exists"] is True
    assert payload["writable"] is True
    assert custom_root.is_dir()

    restarted = TestClient(create_app(database_url))
    persisted = restarted.get("/api/professional-intelligence/evidence-root")
    assert persisted.status_code == 200
    assert persisted.json()["root_path"] == str(custom_root.resolve())


def test_concurrent_evidence_root_and_readiness_provision_one_default(tmp_path: Path) -> None:
    client = _client(tmp_path)
    barrier = Barrier(2)

    def request(path: str):
        barrier.wait(timeout=5)
        return client.get(path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        evidence_future = executor.submit(
            request, "/api/professional-intelligence/evidence-root"
        )
        readiness_future = executor.submit(
            request, "/api/professional-intelligence/execution-readiness"
        )
        evidence = evidence_future.result(timeout=10)
        readiness = readiness_future.result(timeout=10)

    assert evidence.status_code == 200
    assert readiness.status_code == 200
    assert evidence.json()["root_path"] == str((tmp_path / "professional-evidence").resolve())
    assert readiness.json()["ready"] is True


def test_evidence_root_rejects_a_file_path(tmp_path: Path) -> None:
    client = _client(tmp_path)
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
