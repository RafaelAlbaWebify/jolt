from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_language_audit_runs_directly_from_repo_root_without_pythonpath() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit-language-hardlines.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "language" in result.stdout.casefold()
