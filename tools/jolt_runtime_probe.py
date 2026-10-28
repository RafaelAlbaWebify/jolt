"""Read-only JOLT runtime health and benchmark probe.

Never starts services, changes database records, or submits POST requests.
Results are redacted and written to one local ZIP.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

API_ROUTES = {
    "health": "/api/health",
    "opportunities": "/api/opportunity-index",
    "market_insights": "/api/market-intelligence",
    "review_inbox": "/api/review-inbox/export",
    "ai_export": "/api/ai-work-package/export",
}
MAX_READ = 40 * 1024 * 1024


def _local_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Only loopback HTTP services are permitted")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Credentials, queries and fragments are not permitted")
    if not parsed.port or parsed.path not in {"", "/"}:
        raise ValueError("Expected a local service origin with an explicit port")
    return url.rstrip("/")


def _request(url: str) -> dict[str, object]:
    started = time.perf_counter()
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            data = response.read(MAX_READ + 1)
            too_large = len(data) > MAX_READ
            status = response.status
            return {
                "ok": 200 <= status < 400 and not too_large,
                "status": status,
                "milliseconds": round((time.perf_counter() - started) * 1000, 2),
                "bytes_read": min(len(data), MAX_READ),
                "truncated": too_large,
            }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "milliseconds": round((time.perf_counter() - started) * 1000, 2),
        }


def _browser(frontend: str) -> dict[str, object]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"state": "unavailable", "reason": "python_playwright_not_installed"}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(type(error).__name__))
                started = time.perf_counter()
                response = page.goto(frontend, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(800)
                elapsed = round((time.perf_counter() - started) * 1000, 2)
                status = response.status if response else None
                return {
                    "state": "passed" if status and status < 400 and not errors else "failed",
                    "http_status": status,
                    "dom_content_loaded_ms": elapsed,
                    "javascript_error_count": len(errors),
                    "body_present": bool(page.locator("body").count()),
                    "scope": "frontend_initial_navigation_only",
                }
            finally:
                browser.close()
    except Exception as exc:
        return {"state": "unavailable", "reason": type(exc).__name__}


def _revision(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, check=True, text=True, timeout=5,
        )
        return result.stdout.strip()[:40]
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def run(root: Path, output: Path, samples: int) -> dict[str, object]:
    state_path = root / ".jolt" / "services.json"
    if not state_path.is_file():
        raise ValueError("JOLT is not running or .jolt/services.json is unavailable")
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    backend = _local_url(state["backend_url"])
    frontend = _local_url(state["frontend_url"])
    health = _request(backend + API_ROUTES["health"])
    identity = _request(backend + "/api/runtime-identity")
    if not health["ok"] or not identity["ok"]:
        raise RuntimeError("Backend health/identity not available; no benchmark was run")
    routes: dict[str, object] = {}
    for label, path in API_ROUTES.items():
        readings = [_request(backend + path) for _ in range(samples + 1)]
        timed = readings[1:]
        valid = [float(item["milliseconds"]) for item in timed if item["ok"]]
        routes[label] = {
            "state": "passed" if len(valid) == samples else "failed",
            "samples": samples,
            "median_ms": round(statistics.median(valid), 2) if valid else None,
            "min_ms": min(valid) if valid else None,
            "max_ms": max(valid) if valid else None,
            "http_statuses": [item.get("status") for item in timed],
            "payload_bytes": [item.get("bytes_read") for item in timed],
            "warmup_ok": bool(readings[0]["ok"]),
            "error_types": [item.get("error_type") for item in timed if not item["ok"]],
        }
    frontend_http = _request(frontend + "/")
    browser = _browser(frontend + "/") if frontend_http["ok"] else {"state": "failed"}
    report = {
        "contract": "jolt_runtime_acceptance",
        "version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "checkout_sha": _revision(root),
        "sample_count": samples,
        "backend_health": health,
        "backend_identity": identity,
        "frontend_http": frontend_http,
        "api_benchmarks": routes,
        "browser": browser,
        "limitations": [
            "Only GET requests were sent; no mutation or live capture was requested",
            "Initial page navigation does not prove all interactive workflows",
            "These are baseline timings, not historical before/after improvements",
            "The script does not start or stop JOLT services",
            "No raw API responses, URLs, job records or browser console text are exported",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("runtime_acceptance.json", json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.samples <= 10:
        parser.error("--samples must be between 1 and 10")
    report = run(args.root.resolve(), args.output.resolve(), args.samples)
    print("Runtime report:", args.output)
    print("API:", {k: v["state"] for k, v in report["api_benchmarks"].items()})
    print("Browser:", report["browser"]["state"])


if __name__ == "__main__":
    main()
