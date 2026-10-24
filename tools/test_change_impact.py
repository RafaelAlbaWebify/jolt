"""Contract tests for the repository impact analyzer."""
from pathlib import Path

from tools.change_impact import analyze, python_imports, relative_js_target


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
