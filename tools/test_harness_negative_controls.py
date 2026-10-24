"""Negative controls proving the harness fails on broken boundaries.

All mutations occur in temporary fixture repositories; never touch JOLT data.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("change_impact.py")
spec = importlib.util.spec_from_file_location("jolt_impact", SCRIPT)
assert spec is not None and spec.loader is not None
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)


def fixture_root(tmp_path: Path) -> Path:
    files = {
        "backend/src/jolt/schemas.py": """
class LinkedInLiveCaptureRequest:
    items: list = Field(max_length=100)
    pages: list = Field(max_length=10)
    requested_item_limit: int = Field(le=100)
class IndeedLiveCaptureRequest:
    items: list = Field(max_length=200)
    pages: list = Field(max_length=20)
    requested_item_limit: int = Field(le=200)
""",
        "backend/src/jolt/consumer.py": "from jolt.schemas import IndeedLiveCaptureRequest\n",
        "backend/tests/test_consumer.py": "from jolt.consumer import x\n",
        "frontend/src/App.tsx": "export default 1\n",
        "frontend/src/capture-limits.json": json.dumps({
            "indeed": {"max_jobs": 200, "max_pages": 20},
            "linkedin": {"max_jobs": 100, "max_pages": 10},
        }),
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def test_positive_control_no_contract_drift(tmp_path: Path):
    root = fixture_root(tmp_path)
    assert impact.capture_contract_risks(root) == []


def test_negative_control_contract_drift_is_detected(tmp_path: Path):
    root = fixture_root(tmp_path)
    path = root / "frontend/src/capture-limits.json"
    limits = json.loads(path.read_text(encoding="utf-8"))
    limits["linkedin"] = {"max_jobs": 200, "max_pages": 20}
    path.write_text(json.dumps(limits), encoding="utf-8")
    failures = impact.capture_contract_risks(root)
    assert len(failures) == 3
    assert all(x["status"] == "incompatible" for x in failures)


def test_negative_control_missing_contract_fails_closed(tmp_path: Path):
    root = fixture_root(tmp_path)
    (root / "frontend/src/capture-limits.json").unlink()
    assert impact.capture_contract_risks(root)[0]["status"] == "unknown"


def test_negative_control_broken_python_import_edge(tmp_path: Path):
    root = fixture_root(tmp_path)
    report = impact.analyze(root, ["backend/src/jolt/schemas.py"])
    assert "backend/src/jolt/consumer.py" in report["direct_dependents"]
    assert "backend/tests/test_consumer.py" in report["test_candidates"]
    (root / "backend/src/jolt/consumer.py").write_text("value = 1\n", encoding="utf-8")
    after = impact.analyze(root, ["backend/src/jolt/schemas.py"])
    assert "backend/src/jolt/consumer.py" not in after["direct_dependents"]
    assert "backend/tests/test_consumer.py" not in after["test_candidates"]
