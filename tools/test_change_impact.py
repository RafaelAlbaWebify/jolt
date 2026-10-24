"""Contract tests for the repository impact analyzer."""
from pathlib import Path

from tools.change_impact import analyze, boundary_edges, capture_contract_risks, python_imports, relative_js_target


def test_python_reverse_dependency_and_test_selection(tmp_path: Path):
    root = tmp_path
    for relative, content in {
        "backend/src/jolt/__init__.py": "",
        "backend/src/jolt/schemas.py": "from pydantic import BaseModel\n",
        "backend/src/jolt/consumer.py": "from jolt.schemas import Job\n",
        "backend/tests/test_consumer.py": "from jolt.consumer import foo\n",
        "frontend/src/App.tsx": "export default function App() {}",
        "tools/launcher.ps1": "",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    result = analyze(root, ["backend/src/jolt/schemas.py"])
    assert "backend/src/jolt/consumer.py" in result["affected_dependents"]
    assert "backend/tests/test_consumer.py" in result["test_candidates"]
    assert result["critical_changed"] == ["backend/src/jolt/schemas.py"]


def test_js_relative_resolution():
    known = {"frontend/src/lib/api.ts", "frontend/src/ui/index.tsx"}
    assert relative_js_target("frontend/src/App.tsx", "./lib/api", known) == "frontend/src/lib/api.ts"
    assert relative_js_target("frontend/src/App.tsx", "./ui", known) == "frontend/src/ui/index.tsx"


def test_python_imports_do_not_invent_nonexistent_targets():
    known = {"backend/src/jolt/a.py"}
    assert python_imports("backend/src/jolt/a.py", "import jolt.not_present", known) == set()


def test_capture_contract_detects_producer_receiver_mismatch(tmp_path: Path):
    import json

    config = tmp_path / "frontend/src/capture-limits.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({
        "indeed": {"max_jobs": 200, "max_pages": 20},
        "linkedin": {"max_jobs": 200, "max_pages": 20},
    }), encoding="utf-8")
    schemas = tmp_path / "backend/src/jolt/schemas.py"
    schemas.parent.mkdir(parents=True)
    schemas.write_text("""
class IndeedLiveCaptureRequest:
    items: list = Field(max_length=200)
    pages: list = Field(max_length=20)
    requested_item_limit: int = Field(le=200)

class LinkedInLiveCaptureRequest:
    items: list = Field(max_length=100)
    pages: list = Field(max_length=10)
    requested_item_limit: int = Field(le=100)
""", encoding="utf-8")
    risks = capture_contract_risks(tmp_path)
    assert len(risks) == 3
    assert {risk["field"] for risk in risks} == {"items", "pages", "requested_item_limit"}
    assert all(risk["source"] == "linkedin" for risk in risks)
    assert all(risk["status"] == "incompatible" for risk in risks)


def test_capture_contract_reports_missing_configuration_as_unknown(tmp_path: Path):
    risks = capture_contract_risks(tmp_path)
    assert risks[0]["status"] == "unknown"


def test_static_http_route_and_db_model_boundaries(tmp_path: Path):
    sources = {
        "backend/src/jolt/main.py": '@app.get("/api/jobs")\ndef jobs(): pass\n',
        "backend/src/jolt/database.py": 'class Posting: pass\n',
        "backend/src/jolt/reader.py": 'from jolt.database import Posting\nitems = Posting\n',
        "frontend/src/App.tsx": 'fetch("/api/jobs")\n',
    }
    for relative, value in sources.items():
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(value, encoding="utf-8")
    graph = boundary_edges(tmp_path, set(sources))
    assert "backend/src/jolt/main.py" in graph["frontend/src/App.tsx"]
    assert "backend/src/jolt/database.py" in graph["backend/src/jolt/reader.py"]
