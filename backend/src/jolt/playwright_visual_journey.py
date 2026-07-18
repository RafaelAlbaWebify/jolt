from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

APP_URL = "http://127.0.0.1:5173"


def _record(
    journey: list[dict[str, object]],
    *,
    step: str,
    expected: str,
    actual: str,
    passed: bool,
    screenshot: str = "",
) -> None:
    journey.append(
        {
            "step": step,
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "screenshot": screenshot,
        }
    )


def _screenshot(
    page: Page,
    output_dir: Path,
    filename: str,
    *,
    full_page: bool = False,
) -> str:
    page.screenshot(path=output_dir / filename, full_page=full_page)
    return filename


def run(output_dir: Path, app_url: str = APP_URL) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots = output_dir / "screenshots"
    screenshots.mkdir(exist_ok=True)

    journey: list[dict[str, object]] = []
    console_messages: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on(
            "console",
            lambda message: console_messages.append(f"{message.type}: {message.text}"),
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        page.goto(app_url, wait_until="domcontentloaded", timeout=60_000)
        page.locator("#root").wait_for(state="attached", timeout=30_000)
        page.wait_for_function(
            "document.body && document.body.innerText.trim().length > 80",
            timeout=60_000,
        )
        top = _screenshot(page, screenshots, "01-workbench-top.png")
        _record(
            journey,
            step="open_workbench",
            expected="The JOLT workbench renders visible content.",
            actual="The root container rendered with visible page content.",
            passed=True,
            screenshot=top,
        )

        total_height = int(page.evaluate("document.documentElement.scrollHeight"))
        viewport_height = int((page.viewport_size or {"height": 1000})["height"])
        positions: list[int] = []
        position = 0
        while position < total_height:
            page.evaluate(
                "value => window.scrollTo({ top: value, behavior: 'instant' })",
                position,
            )
            page.wait_for_timeout(250)
            positions.append(position)
            position += max(500, viewport_height - 150)
            total_height = int(page.evaluate("document.documentElement.scrollHeight"))
        page.evaluate("window.scrollTo({ top: 0, behavior: 'instant' })")
        full = _screenshot(page, screenshots, "02-workbench-full.png", full_page=True)
        _record(
            journey,
            step="review_full_workbench",
            expected="A reviewer can traverse the full workbench without a page error.",
            actual=f"Reviewed {len(positions)} scroll positions.",
            passed=not page_errors,
            screenshot=full,
        )

        details = page.locator("details")
        expanded = False
        if details.count() > 0:
            first = details.first
            first.scroll_into_view_if_needed(timeout=5_000)
            first.evaluate("element => { element.open = true; }")
            page.wait_for_timeout(300)
            expanded = first.get_attribute("open") is not None
        expanded_shot = _screenshot(page, screenshots, "03-expanded-details.png")
        _record(
            journey,
            step="expand_first_details_panel",
            expected="The first available details panel can be expanded.",
            actual="Expanded successfully."
            if expanded
            else "No expandable details panel was available.",
            passed=expanded or details.count() == 0,
            screenshot=expanded_shot,
        )

        buttons = page.get_by_role("button")
        button_count = buttons.count()
        _record(
            journey,
            step="inspect_controls",
            expected="Interactive controls are discoverable through accessible roles.",
            actual=f"Found {button_count} buttons.",
            passed=button_count > 0,
        )

        browser.close()

    findings: list[dict[str, str]] = []
    for error in page_errors:
        findings.append({"severity": "error", "message": f"Browser page error: {error}"})
    for item in journey:
        if not item["passed"]:
            findings.append(
                {
                    "severity": "error",
                    "message": f"Visual journey step failed: {item['step']}: {item['actual']}",
                }
            )

    summary: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "app_url": app_url,
        "result": "failed" if findings else "passed",
        "journey": journey,
        "console_messages": console_messages,
        "page_errors": page_errors,
        "findings": findings,
    }
    (output_dir / "playwright-journey.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the JOLT visual-review Playwright journey.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--app-url", default=APP_URL)
    args = parser.parse_args()
    summary = run(args.output_dir, args.app_url)
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if summary["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
