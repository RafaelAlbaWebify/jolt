"""Contract tests for the read-only discovery architecture diagnosis."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "diagnose_discovery_pipeline.py"
spec = importlib.util.spec_from_file_location("discovery_diagnosis", SCRIPT)
assert spec is not None and spec.loader is not None
diagnosis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnosis)


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_portal_import_path_and_readonly_report(tmp_path: Path) -> None:
    _run("init", cwd=tmp_path)
    backend = tmp_path / "backend" / "src" / "jolt"
    backend.mkdir(parents=True)
    (backend / "linkedin_capture.py").write_text(
        "from jolt.capture_ingestion import ingest_capture_item\n"
        "def get_description():\n    return 'description'\n", encoding="utf-8"
    )
    (backend / "capture_ingestion.py").write_text(
        "def ingest_capture_item():\n    return None\n", encoding="utf-8"
    )
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "Discovery.tsx").write_text(
        "export const Discovery = () => null;\n", encoding="utf-8"
    )
    _run("add", ".", cwd=tmp_path)
    report = diagnosis.build_report(tmp_path)
    assert report["scope"] == "STATIC_SOURCE_ONLY"
    assert report["safety"]["database_opened"] is False
    assert report["safety"]["portals_contacted"] is False
    assert report["portal_inventory"]["linkedin"]["backend_modules"] == ["jolt.linkedin_capture"]
    edges = report["portal_inventory"]["linkedin"]["static_import_paths_to_shared_modules"]
    assert any(e["to"] == "jolt.capture_ingestion" for e in edges)
    assert report["entrypoints"]["frontend_candidates"] == ["frontend/src/Discovery.tsx"]
    assert not (tmp_path / ".jolt").exists()


def test_bad_python_is_explicitly_reported(tmp_path: Path) -> None:
    _run("init", cwd=tmp_path)
    package = tmp_path / "backend" / "src" / "jolt"
    package.mkdir(parents=True)
    (package / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    _run("add", ".", cwd=tmp_path)
    report = diagnosis.build_report(tmp_path)
    assert len(report["parse_errors"]) == 1
    assert report["parse_errors"][0]["path"] == "backend/src/jolt/broken.py"
