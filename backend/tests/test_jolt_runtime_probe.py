from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest


def _probe():
    source = Path(__file__).resolve().parents[2] / "tools" / "jolt_runtime_probe.py"
    spec = importlib.util.spec_from_file_location("jolt_runtime_probe", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_url_rejects_non_loopback_and_credentials() -> None:
    probe = _probe()
    assert probe._local_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    with pytest.raises(ValueError, match="loopback"):
        probe._local_url("https://example.com")
    with pytest.raises(ValueError, match="Credentials"):
        probe._local_url("http://user:secret@localhost:8000")


def test_runtime_probe_redacts_responses_and_writes_one_zip(tmp_path: Path, monkeypatch) -> None:
    probe = _probe()
    state = tmp_path / ".jolt" / "services.json"
    state.parent.mkdir()
    state.write_text(
        json.dumps(
            {
                "backend_url": "http://127.0.0.1:8000",
                "frontend_url": "http://127.0.0.1:5173",
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def request(url):
        calls.append(url)
        return {
            "ok": True,
            "status": 200,
            "milliseconds": 20.0,
            "bytes_read": 16,
            "secret": "private-response-not-exported",
        }

    monkeypatch.setattr(probe, "_request", request)
    monkeypatch.setattr(
        probe,
        "_browser",
        lambda url: {"state": "passed", "scope": "frontend_initial_navigation_only"},
    )
    output = tmp_path / "acceptance.zip"
    report = probe.run(tmp_path, output, 3)
    assert all(item["state"] == "passed" for item in report["api_benchmarks"].values())
    assert report["api_benchmarks"]["market_insights"]["median_ms"] == 20
    with ZipFile(output) as archive:
        assert archive.namelist() == ["runtime_acceptance.json"]
        payload = archive.read("runtime_acceptance.json").decode()
    assert "private-response-not-exported" not in payload
    assert state.is_file()
    assert all(url.startswith("http://127.0.0.1:") for url in calls)
