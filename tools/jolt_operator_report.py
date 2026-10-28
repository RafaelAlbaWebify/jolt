"""Generate a redacted, read-only JOLT operator diagnostic ZIP.

Example: python tools/jolt_operator_report.py backend/data/jolt.db --output JOLT_DIAGNOSTIC.zip
No backend service, credentials, browser session or source descriptions are accessed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def _baseline_module():
    source = Path(__file__).with_name("jolt_baseline.py")
    spec = importlib.util.spec_from_file_location("jolt_baseline", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the JOLT baseline diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_revision(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    sha = result.stdout.strip()
    return sha if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha) else None


def build_report(database: Path, project_root: Path) -> dict[str, object]:
    baseline = _baseline_module().collect(database)
    return {
        "contract": "jolt_operator_diagnostic",
        "version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "checkout_sha": _git_revision(project_root),
        "data_origin": "local_sqlite_read_only",
        "runtime_api_verified": False,
        "browser_verified": False,
        "database": baseline,
        "limitations": [
            "No backend API or frontend checks have been executed",
            "No capture text, application contents, identities or logs are included",
            "Row counts are snapshots; concurrent database writes may change them",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.database.resolve():
        parser.error("Output must differ from database")
    report = build_report(args.database, Path(__file__).resolve().parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(report, indent=2, sort_keys=True))
    print(f"Diagnostic created: {args.output}")


if __name__ == "__main__":
    main()
