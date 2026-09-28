from __future__ import annotations

from pathlib import Path


def _runner_text() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / "tools" / "run-linkedin-search-experiment-v2.ps1").read_text(
        encoding="utf-8"
    )


def test_v2_runner_only_reuses_experiment_owned_saved_searches() -> None:
    runner = _runner_text()

    assert "function Test-ExperimentOwnedSearch" in runner
    assert '($label -like "EXP *" -or $label -like "EXP2 *")' in runner
    assert 'notes -like "Controlled LinkedIn search experiment*"' in runner

    assert "$canonicalMatches" in runner
    assert "$experimentMatches" in runner
    assert "Where-Object { Test-ExperimentOwnedSearch $_ }" in runner
    assert "Refusing to reuse canonical criteria owned by a non-experiment saved search" in runner


def test_v2_runner_refuses_to_retire_non_experiment_searches() -> None:
    runner = _runner_text()

    assert "if (-not (Test-ExperimentOwnedSearch $search))" in runner
    assert "Refusing to retire non-experiment saved search" in runner
