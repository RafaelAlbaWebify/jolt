from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from playwright.sync_api import Page, sync_playwright

APP_URL = "http://127.0.0.1:5173"
API_URL = "http://127.0.0.1:8000"
MAX_SCROLL_STEPS = 200
VIEW_SPECS = (
    ("opportunities", "Opportunities", "Opportunity review workbench"),
    ("applications", "Applications", "Application management"),
    ("evidence", "Evidence", "Duplicate and source identity evidence"),
)


class ViewAudit(TypedDict):
    view: str
    label: str
    expected_heading: str
    heading_visible: bool
    data_ready: bool
    visible_button_count: int
    scroll_position_count: int
    screenshot: str


def _get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _visible_button_count(page: Page) -> int:
    buttons = page.get_by_role("button")
    return sum(1 for index in range(buttons.count()) if buttons.nth(index).is_visible())


def _review_scroll_positions(page: Page) -> list[int]:
    viewport_height = int((page.viewport_size or {"height": 1000})["height"])
    step = max(500, viewport_height - 150)
    positions: list[int] = []
    position = 0

    for _ in range(MAX_SCROLL_STEPS):
        total_height = int(page.evaluate("document.documentElement.scrollHeight"))
        if position >= total_height:
            break
        page.evaluate(
            "value => window.scrollTo({ top: value, behavior: 'instant' })",
            position,
        )
        page.wait_for_timeout(150)
        positions.append(position)
        position += step
    else:
        raise RuntimeError(
            f"Workspace scrolling exceeded the safety limit of {MAX_SCROLL_STEPS} steps."
        )

    page.evaluate("() => window.scrollTo({ top: 0, behavior: 'instant' })")
    return positions


def _wait_for_view_data(
    page: Page,
    *,
    view_id: str,
    opportunity_count: int,
    first_title: str,
    application_candidate_count: int,
    first_application_title: str,
) -> bool:
    if view_id == "opportunities":
        expected_text = f"all ({opportunity_count})"
    elif view_id == "applications":
        expected_text = (
            first_application_title
            if application_candidate_count > 0
            else "No pursued or active applications are available."
        )
    else:
        expected_text = (
            first_title
            if opportunity_count > 0
            else "No opportunity identity evidence is available."
        )

    page.wait_for_function(
        "expectedText => (document.body?.innerText || '').includes(expectedText)",
        arg=expected_text,
        timeout=60_000,
    )
    return expected_text in page.locator("body").inner_text()


def run(
    output_dir: Path,
    app_url: str = APP_URL,
    api_url: str = API_URL,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots = output_dir / "workspace-screenshots"
    screenshots.mkdir(exist_ok=True)

    opportunities = _get_json(f"{api_url.rstrip('/')}/api/opportunities")
    if not isinstance(opportunities, list):
        raise RuntimeError("Opportunity API did not return a list.")
    opportunity_count = len(opportunities)

    first_title = ""
    if opportunities and isinstance(opportunities[0], dict):
        first_title = str(opportunities[0].get("title") or "").strip()

    application_candidates = [
        item
        for item in opportunities
        if isinstance(item, dict)
        and (item.get("review_decision") == "pursue" or bool(item.get("application_id")))
    ]
    first_application_title = ""
    if application_candidates:
        first_application_title = str(application_candidates[0].get("title") or "").strip()

    page_errors: list[str] = []
    console_messages: list[str] = []
    views: list[ViewAudit] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "console",
                lambda message: console_messages.append(f"{message.type}: {message.text}"),
            )
            page.goto(app_url, wait_until="domcontentloaded", timeout=60_000)
            page.locator("#root").wait_for(state="attached", timeout=30_000)
            page.get_by_role("navigation", name="JOLT workspace views").wait_for(
                state="visible",
                timeout=30_000,
            )

            for view_id, label, expected_heading in VIEW_SPECS:
                button = page.get_by_role("button", name=label, exact=True)
                button.click(timeout=5_000)
                heading = page.get_by_role("heading", name=expected_heading, exact=True)
                heading.wait_for(state="visible", timeout=30_000)
                data_ready = _wait_for_view_data(
                    page,
                    view_id=view_id,
                    opportunity_count=opportunity_count,
                    first_title=first_title,
                    application_candidate_count=len(application_candidates),
                    first_application_title=first_application_title,
                )
                page.wait_for_timeout(300)

                positions = _review_scroll_positions(page)
                visible_buttons = _visible_button_count(page)
                screenshot_name = f"workspace-{view_id}.png"
                page.screenshot(path=screenshots / screenshot_name, full_page=True)
                views.append(
                    {
                        "view": view_id,
                        "label": label,
                        "expected_heading": expected_heading,
                        "heading_visible": heading.is_visible(),
                        "data_ready": data_ready,
                        "visible_button_count": visible_buttons,
                        "scroll_position_count": len(positions),
                        "screenshot": f"workspace-screenshots/{screenshot_name}",
                    }
                )
        finally:
            browser.close()

    findings = [
        {"severity": "error", "message": f"Browser page error: {error}"} for error in page_errors
    ]
    for view in views:
        if not view["heading_visible"]:
            findings.append(
                {
                    "severity": "error",
                    "message": f"Workspace heading was not visible for {view['view']}.",
                }
            )
        if not view["data_ready"]:
            findings.append(
                {
                    "severity": "error",
                    "message": f"Workspace data did not finish loading for {view['view']}.",
                }
            )

    measurement_valid = opportunity_count > 0 and all(view["data_ready"] for view in views)
    if opportunity_count < 1:
        findings.append(
            {
                "severity": "warning",
                "message": (
                    "The opportunity dataset is empty. Navigation rendering is valid, but control "
                    "and scroll counts are not valid populated before/after redesign evidence."
                ),
            }
        )

    has_errors = any(item["severity"] == "error" for item in findings)
    summary: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "app_url": app_url,
        "api_url": api_url,
        "viewport": {"width": 1440, "height": 1000},
        "result": "failed" if has_errors else "passed",
        "opportunity_count": opportunity_count,
        "application_candidate_count": len(application_candidates),
        "measurement_valid": measurement_valid,
        "views": views,
        "total_visible_buttons_across_views": sum(view["visible_button_count"] for view in views),
        "total_scroll_positions_across_views": sum(view["scroll_position_count"] for view in views),
        "console_messages": console_messages,
        "page_errors": page_errors,
        "findings": findings,
    }
    (output_dir / "workspace-navigation-audit.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit JOLT workspace navigation views.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--app-url", default=APP_URL)
    parser.add_argument("--api-url", default=API_URL)
    args = parser.parse_args()

    try:
        summary = run(args.output_dir, args.app_url, args.api_url)
    except Exception as exc:  # noqa: BLE001
        summary = {
            "generated_at": datetime.now(UTC).isoformat(),
            "app_url": args.app_url,
            "api_url": args.api_url,
            "result": "failed",
            "views": [],
            "console_messages": [],
            "page_errors": [],
            "findings": [{"severity": "error", "message": f"Workspace audit crashed: {exc}"}],
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "workspace-navigation-audit.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
        )

    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if summary["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
