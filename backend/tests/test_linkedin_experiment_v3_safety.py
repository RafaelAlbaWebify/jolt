from __future__ import annotations

from pathlib import Path


def _runner_text() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / "tools" / "run-linkedin-search-experiment-v3.ps1").read_text(
        encoding="utf-8"
    )


def test_v3_runner_keeps_production_searches_read_only() -> None:
    runner = _runner_text()

    assert 'owner = "production"' in runner
    assert 'Write-Host "READ-ONLY production: $($saved.label)"' in runner
    assert (
        "$experimentIds += $saved.id"
        not in runner.split('if ($definition.owner -eq "production")')[1].split("continue")[0]
    )


def test_v3_runner_uses_batch_capture_overrides() -> None:
    runner = _runner_text()

    assert "max_jobs_override = $MaxJobs" in runner
    assert "max_pages_override = $MaxPages" in runner
    assert "Only EXP3-owned comparator searches were retired" in runner
