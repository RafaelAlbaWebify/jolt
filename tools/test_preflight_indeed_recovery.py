"""Recovery preflight operates exclusively on ZIP evidence, never on live data."""
import json
import zipfile
from pathlib import Path

import pytest

import importlib.util

SCRIPT = Path(__file__).with_name("preflight-indeed-recovery.py")
spec = importlib.util.spec_from_file_location("preflight_indeed_recovery", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
inspect_archive = module.inspect_archive


def archive_with_payload(path: Path, items: list[dict]) -> None:
    payload = {"search_url": "https://es.indeed.com/jobs?q=testing",
               "items": items, "pages": [{"page_number": 1}],
               "requested_item_limit": 200}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("api_result.json", json.dumps({
            "validation_errors": [{"input": payload, "type": "too_long"}]
        }))


def item(key: str) -> dict:
    return {"source_job_id": key, "identity_verified": True,
            "description": "Verified detail text"}


def test_recovery_payload_from_validation_error(tmp_path: Path):
    path = tmp_path / "evidence.zip"
    archive_with_payload(path, [item(f"job-{i}") for i in range(161)])
    result = inspect_archive(path)
    assert result["item_count"] == 161
    assert result["requested_item_limit"] == 200
    assert result["all_descriptions_present"]


def test_recovery_rejects_duplicate_identity(tmp_path: Path):
    path = tmp_path / "evidence.zip"
    archive_with_payload(path, [item("same"), item("same")])
    with pytest.raises(ValueError, match="Duplicate"):
        inspect_archive(path)


def test_recovery_rejects_unverified_identity(tmp_path: Path):
    path = tmp_path / "evidence.zip"
    archive_with_payload(path, [{**item("job-1"), "identity_verified": False}])
    with pytest.raises(ValueError, match="unverified"):
        inspect_archive(path)
