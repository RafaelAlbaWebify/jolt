from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Route, sync_playwright

APP_URL = "http://127.0.0.1:5173"
VIEWPORT = {"width": 1680, "height": 945}
WORKSPACES = (
    ("Capture Jobs", "Capture Jobs"),
    ("Review Inbox", "Review Inbox"),
    ("Applications", "Application Pipeline"),
    ("LinkedIn Profile", "LinkedIn Profile"),
    ("Market Insights", "Market Insights"),
    ("Settings & Data", "Settings & Data"),
)
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def visible_controls(page: Page) -> list[dict[str, Any]]:
    return page.evaluate(
        r"""() => {
            const root = [...document.querySelectorAll('.workspace-view')]
                .find((node) => !node.hasAttribute('hidden'));
            if (!root) return [];
            const selector = 'button, a[href], input, select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])';
            return [...root.querySelectorAll(selector)]
                .filter((el) => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
                })
                .map((el) => {
                    const aria = el.getAttribute('aria-label');
                    const labelled = el.getAttribute('aria-labelledby');
                    let label = aria || '';
                    if (!label && labelled) {
                        label = labelled.split(/\s+/)
                            .map((id) => document.getElementById(id)?.textContent || '')
                            .join(' ')
                            .trim();
                    }
                    if (!label) label = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 160);
                    if (!label && 'name' in el) label = el.name || '';
                    return {
                        tag: el.tagName.toLowerCase(),
                        role: el.getAttribute('role'),
                        label,
                        disabled: Boolean(el.disabled) || el.getAttribute('aria-disabled') === 'true',
                    };
                });
        }"""
    )


def workspace_metrics(page: Page) -> dict[str, Any]:
    return page.evaluate(
        r"""() => {
            const root = [...document.querySelectorAll('.workspace-view')]
                .find((node) => !node.hasAttribute('hidden'));
            const shell = document.querySelector('.workspace-shell');
            const sidebar = document.querySelector('.workspace-sidebar');
            const content = document.querySelector('.workspace-content');
            if (!root || !shell || !sidebar || !content) throw new Error('Incomplete workspace shell');

            const box = (el) => {
                const r = el.getBoundingClientRect();
                return {top:r.top,right:r.right,bottom:r.bottom,left:r.left,width:r.width,height:r.height};
            };
            const viewportW = window.innerWidth;
            const viewportH = window.innerHeight;
            const rootBox = root.getBoundingClientRect();

            const clipped = [...root.querySelectorAll('*')].filter((el) => {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                if (r.width <= 0 || r.height <= 0 || s.display === 'none' || s.visibility === 'hidden') return false;
                return r.right > viewportW + 1 || r.left < -1;
            }).slice(0, 25).map((el) => ({
                tag: el.tagName.toLowerCase(),
                className: String(el.className || '').slice(0, 120),
                text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 120),
                rect: box(el),
            }));

            const smallTargets = [...root.querySelectorAll('button, a[href], input, select, [role="button"]')]
                .filter((el) => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'
                        && (r.width < 32 || r.height < 32);
                }).slice(0, 25).map((el) => ({
                    tag: el.tagName.toLowerCase(),
                    text: (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 120),
                    rect: box(el),
                }));

            return {
                viewport: {width: viewportW, height: viewportH},
                document: {
                    clientWidth: document.documentElement.clientWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    clientHeight: document.documentElement.clientHeight,
                    scrollHeight: document.documentElement.scrollHeight,
                },
                shell: box(shell),
                sidebar: box(sidebar),
                content: box(content),
                activeWorkspace: {
                    rect: box(root),
                    clientWidth: root.clientWidth,
                    scrollWidth: root.scrollWidth,
                    clientHeight: root.clientHeight,
                    scrollHeight: root.scrollHeight,
                },
                horizontalDocumentOverflow: Math.max(0, document.documentElement.scrollWidth - viewportW),
                verticalDocumentOverflow: Math.max(0, document.documentElement.scrollHeight - viewportH),
                horizontalWorkspaceOverflow: Math.max(0, root.scrollWidth - root.clientWidth),
                verticalWorkspaceOverflow: Math.max(0, root.scrollHeight - root.clientHeight),
                horizontallyClippedElements: clipped,
                smallInteractiveTargets: smallTargets,
            };
        }"""
    )


def focus_order(page: Page, maximum: int = 30) -> list[dict[str, str]]:
    page.locator("body").click(position={"x": 1, "y": 1})
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for _ in range(maximum):
        page.keyboard.press("Tab")
        item = page.evaluate(
            r"""() => {
                const el = document.activeElement;
                if (!el) return {tag:'', label:''};
                const label = el.getAttribute('aria-label')
                    || (el.textContent || '').trim().replace(/\s+/g, ' ')
                    || el.getAttribute('name')
                    || '';
                return {tag: el.tagName.toLowerCase(), label: label.slice(0, 160)};
            }"""
        )
        key = f"{item['tag']}|{item['label']}"
        if key in seen:
            break
        seen.add(key)
        result.append(item)
    return result


def audit(output_dir: Path, headed: bool) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots = output_dir / "screenshots"
    screenshots.mkdir(exist_ok=True)

    console_errors: list[dict[str, Any]] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []
    http_errors: list[str] = []
    blocked_mutations: list[str] = []
    workspace_results: dict[str, Any] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        context = browser.new_context(viewport=VIEWPORT)

        def readonly_guard(route: Route) -> None:
            request = route.request
            if request.method.upper() in MUTATING_METHODS:
                blocked_mutations.append(f"{request.method} {request.url}")
                route.abort("blockedbyclient")
                return
            route.continue_()

        context.route("**/*", readonly_guard)
        page = context.new_page()
        page.on(
            "console",
            lambda message: console_errors.append({"text": message.text, "location": message.location})
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("requestfailed", lambda request: failed_requests.append(f"{request.method} {request.url}: {request.failure}"))
        page.on(
            "response",
            lambda response: http_errors.append(f"{response.status} {response.request.method} {response.url}")
            if response.status >= 400
            else None,
        )

        page.goto(APP_URL, wait_until="networkidle", timeout=60_000)
        page.get_by_role("button", name="Capture Jobs", exact=True).wait_for(timeout=30_000)

        for index, (label, heading) in enumerate(WORKSPACES, start=1):
            page.get_by_role("button", name=label, exact=True).click()
            page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=30_000)
            page.wait_for_timeout(500)

            metrics = workspace_metrics(page)
            controls = visible_controls(page)
            focus = focus_order(page)
            workspace_results[label] = {
                "heading": heading,
                "metrics": metrics,
                "visible_controls": controls,
                "focus_order": focus,
            }

            base = f"{index:02d}-{slug(label)}"
            page.screenshot(path=screenshots / f"{base}-viewport.png", full_page=False)
            page.screenshot(path=screenshots / f"{base}-full.png", full_page=True)

        context.close()
        browser.close()

    summary = {
        "audit": "JOLT live UI read-only Playwright audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "app_url": APP_URL,
        "viewport": VIEWPORT,
        "read_only_enforcement": {
            "mutating_methods_blocked": sorted(MUTATING_METHODS),
            "blocked_mutation_requests": blocked_mutations,
        },
        "workspaces": workspace_results,
        "diagnostics": {
            "console_errors": console_errors,
            "page_errors": page_errors,
            "failed_requests": failed_requests,
            "http_errors": http_errors,
        },
    }
    (output_dir / "live-ui-audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Playwright audit of the currently running JOLT UI.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--headed", action="store_true", help="Show Chromium while the audit runs.")
    args = parser.parse_args()
    audit(args.output_dir, args.headed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
