"""Regression tests for the Indeed subprocess output contract; no browser or network."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from jolt import discovery_execution as execution


def test_indeed_supervisor_reads_utf8_and_reports_progress(monkeypatch, tmp_path: Path):
    # Real subprocess writes UTF-8 characters not representable in cp1252.
    writer = (
        "import sys;"
        "sys.stdout.buffer.write("
        "'Capturing job 1/200: H₃O⁺ · Médico\\n"
        "Progress: page 1/20 · captured 1/200\\n'.encode('utf-8'))"
    )
    real_popen = subprocess.Popen

    def fake_popen(_command, **kwargs):
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        return real_popen(
            [sys.executable, "-c", writer],
            stdout=kwargs["stdout"],
            stderr=kwargs["stderr"],
            text=kwargs["text"],
            encoding=kwargs["encoding"],
            errors=kwargs["errors"],
            bufsize=kwargs["bufsize"],
        )

    monkeypatch.setattr(execution.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(execution.shutil, "which", lambda name: "pwsh")
    monkeypatch.setattr(execution, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(execution, "_capture_run_id", lambda path: "synthetic-run")
    # The runner only uses the search fields below.
    search = SimpleNamespace(
        definition_json=json.dumps({"search_url": "https://es.indeed.com/jobs?q=test", "max_pages": 20}),
        max_jobs=200,
    )
    phases = []
    result = execution.run_indeed_saved_search(
        search, "synthetic-execution", phase_callback=lambda *args: phases.append(args)
    )
    assert result == "synthetic-run"
    assert ("capturing", 1, 1) in phases


def test_indeed_supervisor_replaces_invalid_utf8(monkeypatch, tmp_path: Path):
    real_popen = subprocess.Popen

    def fake_popen(_command, **kwargs):
        return real_popen(
            [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'bad \\xff byte\\n')"],
            stdout=kwargs["stdout"], stderr=kwargs["stderr"],
            text=kwargs["text"], encoding=kwargs["encoding"],
            errors=kwargs["errors"], bufsize=kwargs["bufsize"],
        )

    monkeypatch.setattr(execution.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(execution.shutil, "which", lambda name: "pwsh")
    monkeypatch.setattr(execution, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(execution, "_capture_run_id", lambda path: "synthetic-run")
    search = SimpleNamespace(
        definition_json=json.dumps({"search_url": "https://es.indeed.com/jobs?q=test", "max_pages": 1}),
        max_jobs=10,
    )
    assert execution.run_indeed_saved_search(search, "synthetic-execution") == "synthetic-run"
