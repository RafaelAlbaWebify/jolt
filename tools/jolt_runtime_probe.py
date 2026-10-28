"""Read-only JOLT runtime health and benchmark probe.

Never starts services, changes database records, or submits POST requests.
Results are redacted and written to one local ZIP.
"""
from __future__ import annotations

import argparse
import json
import re
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
    "review_inbox": "/api/exports/review-inbox-ai-exchange",
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
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "error_type": "HTTPError",
            "milliseconds": round((time.perf_counter() - started) * 1000, 2),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "milliseconds": round((time.perf_counter() - started) * 1000, 2),
        }


def _safe_metrics(measurement: dict[str, object]) -> dict[str, object]:
    """Explicit allowlist: never serialize unexpected response fields."""
    allowed = {
        "ok", "status", "milliseconds", "bytes_read", "truncated", "error_type"
    }
    return {key: value for key, value in measurement.items() if key in allowed}


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


_TRACE_PATTERN = re.compile(
    r"(review_data_load_seconds|review_job_transform_seconds|"
    r"review_index_seconds|review_provenance_seconds|review_payload_build_seconds|"
    r"review_export_ai_payload_seconds|review_export_context_seconds|"
    r"review_export_total_seconds|market_dedup_seconds|"
    r"market_build_pre_aggregation_seconds|unified_exchange_section)"
    r"=([a-z_]+|[0-9]+(?:\.[0-9]+)?)"
)
_TRACE_NUMBERS = re.compile(r"\b(?:seconds|pending|groups|input_count|canonical_count|bytes)"
                            r"=([0-9]+(?:\.[0-9]+)?)")


def _performance_trace(root: Path) -> dict[str, object]:
    """Extract only numeric performance counters from local JOLT backend logs."""
    log_dir = root / ".jolt" / "logs"
    matches: list[dict[str, object]] = []
    for filename in ("backend.err.log", "backend.out.log"):
        path = log_dir / filename
        if not path.is_file():
            continue
        # Tail only: bounded memory, no raw log lines are exported.
        with path.open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 1024 * 1024))
            chunk = stream.read().decode("utf-8", errors="replace")
        for line in chunk.splitlines():
            found = _TRACE_PATTERN.search(line)
            if found is None:
                continue
            entry: dict[str, object] = {"stage": found.group(1)}
            if found.group(1) == "unified_exchange_section":
                entry["section"] = found.group(2)
            else:
                entry["seconds"] = float(found.group(2))
            values = _TRACE_NUMBERS.findall(line)
            if values and "seconds" not in entry:
                entry["seconds"] = float(values[0])
            matches.append(entry)
    return {"state": "available" if matches else "no_stage_traces", "entries": matches[-80:]}


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
        "backend_health": _safe_metrics(health),
        "backend_identity": _safe_metrics(identity),
        "frontend_http": _safe_metrics(frontend_http),
        "api_benchmarks": routes,
        "browser": browser,
        "performance_stages": _performance_trace(root),
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
