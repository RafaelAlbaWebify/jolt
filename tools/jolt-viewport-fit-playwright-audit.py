from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

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
            const shellBox = shell.getBoundingClientRect();
            const sidebarBox = sidebar.getBoundingClientRect();
            const contentBox = content.getBoundingClientRect();
            const activeBox = active.getBoundingClientRect();
            const visibleElements = [...active.querySelectorAll('*')].filter((node) => {
                const style = getComputedStyle(node);
                const box = node.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
            });
            const furthestBottom = Math.max(activeBox.bottom, ...visibleElements.map((node) => node.getBoundingClientRect().bottom));
            const furthestRight = Math.max(activeBox.right, ...visibleElements.map((node) => node.getBoundingClientRect().right));
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
        failures.append(f"visible content below viewport={metrics['verticalOverflow']:.1f}px")
    if metrics["horizontalOverflow"] > 1:
        failures.append(f"visible content beyond viewport={metrics['horizontalOverflow']:.1f}px")
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
    metrics: dict[str, dict[str, Any]] = {}
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("requestfailed", lambda request: failed_requests.append(f"{request.method} {request.url}: {request.failure}"))
        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)

        for sequence, (label, heading) in enumerate(WORKSPACES.items(), start=1):
            page.get_by_role("button", name=label, exact=True).click()
            page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=30_000)
            page.wait_for_timeout(250)
            workspace_metrics = inspect_workspace(page, label)
            metrics[label] = workspace_metrics
            page.screenshot(path=screenshots / f"{sequence:02d}-{label.lower().replace(' ', '-')}.png", full_page=False)
            assert_workspace_fits(workspace_metrics)

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
        "workspaces": metrics,
        "browser_diagnostics": {
            "console_errors": console_errors,
            "page_errors": page_errors,
            "failed_requests": failed_requests,
        },
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


