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
WORKSPACES = {
    "Capture Jobs": "Capture Jobs",
    "Review Inbox": "Review Inbox",
    "Applications": "Application Pipeline",
    "LinkedIn Profile": "LinkedIn Profile",
    "Market Insights": "Market Insights",
    "Settings & Data": "Settings & Data",
}


def request_json(method: str, path: str, payload: dict[str, object] | None = None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    request = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc


def seed_high_volume_applications(count: int = 12) -> None:
    stamp = time.time_ns()
    for index in range(count):
        title = (
            f"Viewport Volume Certification {index + 1:02d} — Senior Application Support, "
            "Cloud Operations and Production Reliability Engineer"
        )
        source_url = f"https://example.test/jobs/viewport-volume-{stamp}-{index}"
        intake = request_json(
            "POST",
            "/api/intake/manual",
            {
                "source_url": source_url,
                "raw_text": (
                    f"{title}\nCertification Systems International and Enterprise Services\n"
                    "Remote across Spain with occasional European customer coordination\n"
                    "Windows Active Directory SQL APIs incident management production support "
                    "customer communication troubleshooting and operational documentation."
                ),
            },
        )
        posting_id = str(intake["posting_id"])
        evaluation_id = str(intake["evaluation_id"])
        request_json(
            "POST",
            f"/api/opportunities/{posting_id}/reviews",
            {"evaluation_id": evaluation_id, "decision": "pursue"},
        )
        application = request_json(
            "POST",
            f"/api/opportunities/{posting_id}/applications",
            {
                "application_url": f"https://example.test/applications/viewport-{stamp}-{index}",
                "resume_used": "Viewport_Certification_Long_Filename_Resume.pdf",
                "notes": "High-volume viewport certification fixture.",
            },
        )
        request_json(
            "POST",
            f"/api/applications/{application['application_id']}/transitions",
            {"status": "submitted", "notes": "Seeded for high-volume viewport certification."},
        )


def inspect_workspace(page: Page, label: str) -> dict[str, Any]:
    return page.evaluate(
        """(label) => {
            const shell = document.querySelector('.workspace-shell');
            const sidebar = document.querySelector('.workspace-sidebar');
            const content = document.querySelector('.workspace-content');
            const active = [...document.querySelectorAll('.workspace-view')]
                .find((node) => !node.hasAttribute('hidden'));
            if (!shell || !sidebar || !content || !active) {
                throw new Error(`Incomplete workspace shell while inspecting ${label}.`);
            }

            const clippedRect = (node) => {
                const rect = node.getBoundingClientRect();
                let top = rect.top;
                let right = rect.right;
                let bottom = rect.bottom;
                let left = rect.left;
                let ancestor = node.parentElement;
                while (ancestor) {
                    const style = getComputedStyle(ancestor);
                    const clipsX = ['hidden', 'auto', 'scroll', 'clip'].includes(style.overflowX);
                    const clipsY = ['hidden', 'auto', 'scroll', 'clip'].includes(style.overflowY);
                    if (clipsX || clipsY) {
                        const ancestorRect = ancestor.getBoundingClientRect();
                        if (clipsX) {
                            left = Math.max(left, ancestorRect.left);
                            right = Math.min(right, ancestorRect.right);
                        }
                        if (clipsY) {
                            top = Math.max(top, ancestorRect.top);
                            bottom = Math.min(bottom, ancestorRect.bottom);
                        }
                    }
                    ancestor = ancestor.parentElement;
                }
                return { top, right, bottom, left, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
            };

            const shellBox = shell.getBoundingClientRect();
            const sidebarBox = sidebar.getBoundingClientRect();
            const contentBox = content.getBoundingClientRect();
            const activeBox = active.getBoundingClientRect();
            const paintedElements = [...active.querySelectorAll('*')]
                .map((node) => ({ node, style: getComputedStyle(node), box: clippedRect(node) }))
                .filter(({ style, box }) => style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0);
            const furthestBottom = Math.max(activeBox.bottom, ...paintedElements.map(({ box }) => box.bottom));
            const furthestRight = Math.max(activeBox.right, ...paintedElements.map(({ box }) => box.right));
            return {
                label,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
                documentClientWidth: document.documentElement.clientWidth,
                documentScrollWidth: document.documentElement.scrollWidth,
                documentClientHeight: document.documentElement.clientHeight,
                documentScrollHeight: document.documentElement.scrollHeight,
                shell: { top: shellBox.top, bottom: shellBox.bottom, left: shellBox.left, right: shellBox.right },
                sidebar: { top: sidebarBox.top, bottom: sidebarBox.bottom, left: sidebarBox.left, right: sidebarBox.right },
                content: { top: contentBox.top, bottom: contentBox.bottom, left: contentBox.left, right: contentBox.right },
                active: {
                    top: activeBox.top,
                    bottom: activeBox.bottom,
                    left: activeBox.left,
                    right: activeBox.right,
                    clientHeight: active.clientHeight,
                    scrollHeight: active.scrollHeight,
                    clientWidth: active.clientWidth,
                    scrollWidth: active.scrollWidth,
                },
                furthestBottom,
                furthestRight,
                verticalOverflow: Math.max(0, furthestBottom - window.innerHeight),
                horizontalOverflow: Math.max(0, furthestRight - window.innerWidth),
                documentVerticalOverflow: Math.max(0, document.documentElement.scrollHeight - window.innerHeight),
                documentHorizontalOverflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
            };
        }""",
        label,
    )


def assert_workspace_fits(metrics: dict[str, Any]) -> None:
    label = str(metrics["label"])
    failures: list[str] = []
    if metrics["documentVerticalOverflow"] > 1:
        failures.append(f"document vertical overflow={metrics['documentVerticalOverflow']:.1f}px")
    if metrics["documentHorizontalOverflow"] > 1:
        failures.append(f"document horizontal overflow={metrics['documentHorizontalOverflow']:.1f}px")
    if metrics["verticalOverflow"] > 1:
        failures.append(f"painted content below viewport={metrics['verticalOverflow']:.1f}px")
    if metrics["horizontalOverflow"] > 1:
        failures.append(f"painted content beyond viewport={metrics['horizontalOverflow']:.1f}px")
    if metrics["active"]["scrollHeight"] > metrics["active"]["clientHeight"] + 1:
        failures.append(
            "active workspace requires vertical scrolling="
            f"{metrics['active']['scrollHeight'] - metrics['active']['clientHeight']}px"
        )
    if metrics["active"]["scrollWidth"] > metrics["active"]["clientWidth"] + 1:
        failures.append(
            "active workspace requires horizontal scrolling="
            f"{metrics['active']['scrollWidth'] - metrics['active']['clientWidth']}px"
        )
    if failures:
        raise AssertionError(f"{label} does not fit {VIEWPORT['width']}x{VIEWPORT['height']}: " + "; ".join(failures))


def audit(output_dir: Path, headed: bool) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots = output_dir / "screenshots"
    screenshots.mkdir(exist_ok=True)
    seed_high_volume_applications()
    metrics: dict[str, dict[str, Any]] = {}
    console_errors: list[dict[str, Any]] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []
    aborted_requests: list[str] = []
    http_errors: list[str] = []

    def record_failed_request(request) -> None:
        detail = f"{request.method} {request.url}: {request.failure}"
        if request.method == "GET" and "ERR_ABORTED" in str(request.failure):
            aborted_requests.append(detail)
        else:
            failed_requests.append(detail)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        page.on(
            "console",
            lambda message: console_errors.append({"text": message.text, "location": message.location})
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("requestfailed", record_failed_request)
        page.on(
            "response",
            lambda response: http_errors.append(f"{response.status} {response.request.method} {response.url}")
            if response.status >= 400
            else None,
        )
        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)

        for sequence, (label, heading) in enumerate(WORKSPACES.items(), start=1):
            page.get_by_role("button", name=label, exact=True).click()
            page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=30_000)
            page.wait_for_timeout(250)
            if label == "Review Inbox":
                visible_rows = page.locator(".opportunity-row:visible").count()
                if visible_rows > 5:
                    raise AssertionError(
                        f"Review Inbox rendered {visible_rows} visible rows; maximum is 5 at 1680x945."
                    )
            if label == "Applications":
                application_count = page.locator("article.application-card").count()
                if application_count < 12:
                    raise AssertionError(
                        f"High-volume Applications fixture was not rendered: expected at least 12 cards, found {application_count}."
                    )
            workspace_metrics = inspect_workspace(page, label)
            metrics[label] = workspace_metrics
            page.screenshot(path=screenshots / f"{sequence:02d}-{label.lower().replace(' ', '-')}.png", full_page=False)
            assert_workspace_fits(workspace_metrics)

        diagnostics = {
            "console_errors": console_errors,
            "page_errors": page_errors,
            "failed_requests": failed_requests,
            "aborted_requests": aborted_requests,
            "http_errors": http_errors,
        }
        (output_dir / "browser-diagnostics.json").write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")

        if http_errors:
            raise AssertionError(f"HTTP resource errors: {http_errors}")
        if console_errors:
            raise AssertionError(f"Browser console errors: {console_errors}")
        if page_errors:
            raise AssertionError(f"Page errors: {page_errors}")
        if failed_requests:
            raise AssertionError(f"Failed browser requests: {failed_requests}")
        context.close()
        browser.close()

    summary = {
        "result": "passed",
        "viewport": VIEWPORT,
        "high_volume_application_count": 12,
        "workspaces": metrics,
        "browser_diagnostics": diagnostics,
    }
    (output_dir / "viewport-fit-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.output_dir, args.headed), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
