from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from jolt.capture_evidence_audit import audit_capture_evidence

API_BASE = "http://127.0.0.1:8000"


def _get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def run(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    captures = _get_json(f"{API_BASE}/api/captures")
    details, findings, metrics = audit_capture_evidence(
        captures,
        lambda run_id: _get_json(f"{API_BASE}/api/captures/{run_id}"),
    )
    summary: dict[str, object] = {
        "status": "failed" if any(item["severity"] == "error" for item in findings) else "passed",
        **metrics,
        "findings": findings,
    }
    (output_dir / "capture-details.json").write_text(
        json.dumps(details, indent=2), encoding="utf-8"
    )
    (output_dir / "capture-audit-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = run(args.output_dir)
    print(json.dumps(summary, indent=2))
    return 1 if summary["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
