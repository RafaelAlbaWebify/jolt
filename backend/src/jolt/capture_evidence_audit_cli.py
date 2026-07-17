from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from jolt.capture_evidence_audit import audit_capture_evidence

API_BASE = "http://127.0.0.1:8000"
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1


def _get_json(url: str) -> object:
    last_error: Exception | None = None
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(  # noqa: S310
                url,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt == REQUEST_ATTEMPTS:
                break
            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"request failed after {REQUEST_ATTEMPTS} attempts: {last_error}"
    ) from last_error


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
