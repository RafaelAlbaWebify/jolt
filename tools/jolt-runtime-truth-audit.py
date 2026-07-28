from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

API_BASE = "http://127.0.0.1:8000"
APP_URL = "http://127.0.0.1:5173"
VIEWPORT = {"width": 1680, "height": 945}


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def read_runtime_identity() -> dict[str, Any]:
    with urllib.request.urlopen(f"{API_BASE}/api/runtime-identity", timeout=30) as response:  # noqa: S310
        loaded = json.loads(response.read().decode("utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError("Runtime identity endpoint did not return an object")
    return loaded


def audit(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    identity = read_runtime_identity()
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []

    assert_true(identity.get("service") == "jolt-backend", "Runtime identity service is not jolt-backend")
    assert_true(bool(identity.get("git", {}).get("repository_root")), "Repository root is missing")
    assert_true(bool(identity.get("git", {}).get("commit_sha")), "Commit SHA is missing")
    assert_true(bool(identity.get("database", {}).get("alembic_revision")), "Alembic revision is missing")
    assert_true(
        identity.get("database", {}).get("record_counts", {}).get("postings") is not None,
        "Posting count is missing",
    )
    assert_true(
        identity.get("database", {}).get("record_counts", {}).get("applications") is not None,
        "Application count is missing",
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda request: failed_requests.append(
                f"{request.method} {request.url}: {request.failure}"
            ),
        )
        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
        page.get_by_text("Runtime identity", exact=True).wait_for(timeout=30_000)
        page.get_by_text("Code", exact=True).wait_for(timeout=30_000)
        page.get_by_text("Database", exact=True).wait_for(timeout=30_000)
        page.get_by_text("Evidence root", exact=True).wait_for(timeout=30_000)
        page.get_by_text("Process", exact=True).wait_for(timeout=30_000)
        page.screenshot(path=output_dir / "runtime-identity-sidebar.png", full_page=True)
        browser.close()

    summary = {
        "runtime_identity": identity,
        "viewport": VIEWPORT,
        "runtime_identity_endpoint_ok": True,
        "runtime_identity_sidebar_visible": True,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed_requests": failed_requests,
    }
    (output_dir / "runtime-truth-audit-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    assert_true(not console_errors, f"Browser console errors: {console_errors}")
    assert_true(not page_errors, f"Page errors: {page_errors}")
    assert_true(not failed_requests, f"Failed browser requests: {failed_requests}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
