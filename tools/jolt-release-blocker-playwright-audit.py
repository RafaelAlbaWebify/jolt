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

        page.get_by_role("button", name="Review Inbox", exact=True).click()
        page.get_by_role("heading", name="Review Inbox", exact=True).wait_for(timeout=30_000)
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

        page.get_by_role("button", name="Capture Jobs", exact=True).click()
        page.get_by_role("heading", name="Capture Jobs", exact=True).wait_for(timeout=30_000)

        primary = page.get_by_role("button", name="Start LinkedIn job capture", exact=True)
        primary.wait_for(timeout=30_000)
        assert_true(primary.is_visible(), "Primary LinkedIn job capture action is not visible")
        assert_true(page.get_by_label("LinkedIn search URL").is_visible(), "LinkedIn search URL field is missing")
        assert_true(page.get_by_label("Maximum jobs").is_visible(), "Maximum jobs setting is missing")
        assert_true(page.get_by_label("Maximum pages").is_visible(), "Maximum pages setting is missing")
        page.get_by_role("heading", name="Profile capture has moved", exact=True).wait_for(timeout=30_000)
        assert_true(
            page.get_by_text(
                "Profile, experience, skills, certifications, and activity belong in LinkedIn Profile.",
                exact=False,
            ).is_visible(),
            "Capture Jobs does not explain the LinkedIn Profile boundary",
        )

        assert_true(
            page.get_by_role("button", name="Start configured-source capture", exact=True).count() == 0,
            "Configured-source capture is still exposed in Capture Jobs",
        )
        assert_true(
            page.get_by_label("Maximum sources").count() == 0,
            "Configured-source limits are still exposed in Capture Jobs",
        )
        assert_true(
            page.locator(".professional-evidence-root").count() == 0,
            "Professional evidence-root settings are still exposed in Capture Jobs",
        )
        assert_true(
            page.get_by_text("Capture history", exact=True).count() == 0,
            "Professional capture history is still exposed in Capture Jobs",
        )
        page.screenshot(path=output_dir / "capture-jobs-boundary.png", full_page=True)

        page.get_by_role("button", name="LinkedIn Profile", exact=True).click()
        page.get_by_role("heading", name="LinkedIn Profile", exact=True).wait_for(timeout=30_000)
        assert_true(
            page.get_by_role("button", name="Capture targets", exact=True).is_visible(),
            "LinkedIn Profile does not expose its profile-capture entry point",
        )
        page.screenshot(path=output_dir / "linkedin-profile-boundary.png", full_page=True)
        browser.close()

    summary = {
        "fixture_title": fixture_title,
        "viewport": VIEWPORT,
        "badge_metrics": badge_metrics,
        "all_score_badges_bounded": True,
        "all_score_labels_human_readable": True,
        "primary_linkedin_capture_action_visible": True,
        "url_and_multipage_settings_visible": True,
        "profile_capture_moved_notice_visible": True,
        "configured_source_capture_absent_from_capture_jobs": True,
        "professional_evidence_root_absent_from_capture_jobs": True,
        "linkedin_profile_workspace_available": True,
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
