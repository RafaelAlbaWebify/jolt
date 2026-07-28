from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

API_BASE = "http://127.0.0.1:8000"
APP_URL = "http://127.0.0.1:5173"
VIEWPORT = {"width": 1680, "height": 945}
DELETE_PHRASE = "DELETE CAPTURE RUN"


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def request_json(method: str, path: str, payload: dict[str, object]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            loaded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError(f"{method} {path} did not return an object")
    return loaded


def seed_pending_opportunity() -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    title = f"Release Blocker UX Audit {stamp}"
    result = request_json(
        "POST",
        "/api/intake/manual",
        {
            "source_url": f"https://example.test/release-blocker/{stamp}",
            "raw_text": (
                f"{title}\nAudit Systems\nRemote Spain\n"
                "Lead technical support engineer responsible for Windows, Active Directory, "
                "incident management, SQL troubleshooting, APIs, logs, customer support, "
                "Microsoft 365, Azure, VMware, documentation, and service management."
            ),
        },
    )
    if not result.get("posting_id"):
        raise RuntimeError("Release-blocker fixture did not return a posting_id")
    return title


def score_badge_metrics(page: Page) -> list[dict[str, Any]]:
    return page.locator(".opportunity-row .score").evaluate_all(
        """badges => badges.map(badge => {
            const span = badge.querySelector('span');
            const box = badge.getBoundingClientRect();
            const spanBox = span?.getBoundingClientRect();
            return {
                className: badge.className,
                rawText: span?.textContent ?? '',
                visibleLabel: span ? getComputedStyle(span, '::after').content.replaceAll('"', '') : '',
                clientWidth: badge.clientWidth,
                scrollWidth: badge.scrollWidth,
                boxWidth: box.width,
                spanWidth: spanBox?.width ?? 0,
                spanScrollWidth: span?.scrollWidth ?? 0,
            };
        })"""
    )


def audit(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_title = seed_pending_opportunity()
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []

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
        page.get_by_role("button", name="Opportunities", exact=True).click()
        page.get_by_role("heading", name="Opportunities", exact=True).wait_for(timeout=30_000)
        page.get_by_text(fixture_title, exact=True).wait_for(timeout=30_000)
        page.locator(".opportunity-row .score").first.wait_for(timeout=30_000)

        badge_metrics = score_badge_metrics(page)
        assert_true(bool(badge_metrics), "No opportunity score badges were rendered")
        for badge in badge_metrics:
            assert_true(
                int(badge["scrollWidth"]) <= int(badge["clientWidth"]) + 1,
                f"Score badge overflows: {badge}",
            )
            assert_true(
                int(badge["spanScrollWidth"]) <= int(badge["clientWidth"]) + 1,
                f"Score label overflows its badge: {badge}",
            )
            assert_true(
                bool(str(badge["visibleLabel"]).strip()),
                f"Score badge has no visible human label: {badge}",
            )
            assert_true(
                "_" not in str(badge["visibleLabel"]),
                f"Score badge exposes a raw enum label: {badge}",
            )
        page.screenshot(path=output_dir / "opportunity-score-badges.png", full_page=True)

        page.get_by_role("button", name="Professional", exact=True).click()
        page.get_by_role("heading", name="Professional", exact=True).wait_for(timeout=30_000)
        evidence_panel = page.locator(".professional-evidence-root")
        evidence_panel.get_by_text("Ready", exact=True).wait_for(timeout=30_000)
        primary = page.get_by_role("button", name="Start new supervised capture", exact=True)
        primary.wait_for(timeout=30_000)
        assert_true(primary.is_visible(), "Primary capture action is not visible")
        page.screenshot(path=output_dir / "professional-ready-and-start-visible.png", full_page=True)

        primary.click()
        page.get_by_text("planned", exact=True).first.wait_for(timeout=30_000)
        page.get_by_label("Authorization phrase for", exact=False).wait_for(timeout=30_000)
        delete_button = page.get_by_role("button", name="Delete this capture batch", exact=True).first
        delete_button.wait_for(timeout=30_000)
        assert_true(delete_button.is_visible(), "Planned capture run has no delete control")
        page.screenshot(path=output_dir / "professional-planned-run-controls.png", full_page=True)

        delete_button.click()
        deletion_input = page.get_by_label("Deletion phrase for", exact=False)
        deletion_input.fill(DELETE_PHRASE)
        permanent_delete = page.get_by_role("button", name="Permanently delete batch", exact=True)
        assert_true(permanent_delete.is_enabled(), "Confirmed deletion action did not become enabled")
        permanent_delete.click()
        page.get_by_text("No capture runs recorded yet", exact=False).wait_for(timeout=30_000)
        page.screenshot(path=output_dir / "professional-run-deleted.png", full_page=True)
        browser.close()

    summary = {
        "fixture_title": fixture_title,
        "viewport": VIEWPORT,
        "badge_metrics": badge_metrics,
        "all_score_badges_bounded": True,
        "all_score_labels_human_readable": True,
        "default_evidence_directory_ready": True,
        "primary_capture_action_visible": True,
        "planned_run_delete_control_visible": True,
        "confirmed_run_deletion_completed": True,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed_requests": failed_requests,
    }
    (output_dir / "release-blocker-audit-summary.json").write_text(
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
