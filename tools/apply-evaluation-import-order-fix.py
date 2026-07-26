from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    backend = root / "backend"
    subprocess.run(
        [
            "uv",
            "run",
            "ruff",
            "check",
            "--select",
            "I",
            "--fix",
            "src/jolt/main.py",
            "src/jolt/opportunity_workbench.py",
        ],
        cwd=backend,
        check=True,
    )
    print("Evaluation import ordering fixed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
