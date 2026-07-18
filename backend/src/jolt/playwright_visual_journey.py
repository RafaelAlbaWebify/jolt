from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import Page, TimeoutError, sync_playwright

APP_URL = "http://127.0.0.1:5173"
API_URL = "http://127.0.0.1:8000"
MAX_SCROLL_STEPS = 200


def _get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


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
    screenshots: Path,
    filename: str,
    *,
    full_page: bool = False,
) -> str:
    page.screenshot(path=screenshots / filename, full_page=full_page)
    return f"screenshots/{filename}"


def _wait_for_loaded_workbench(page: Page, expected_count: int, first_title: str) -> None:
    if expected_count < 1:
        raise RuntimeError("Visual certification requires at least one opportunity.")
    page.locator("#root").wait_for(state="attached", timeout=30_000)
    page.wait_for_function(
        """([expectedCount, expectedTitle]) => {
            const text = document.body?.innerText || "";
            const countReady = text.includes(`all (${expectedCount})`);
            const titleReady = Boolean(expectedTitle) && text.includes(expectedTitle);
            return countReady || titleReady;
        }""",
        arg=[expected_count, first_title],
        timeout=60_000,
    )


def _scroll_like_reviewer(page: Page) -> list[int]:
    viewport_height = int((page.viewport_size or {"height": 1000})["height"])
    step = max(500, viewport_height - 150)
    positions: list[int] = []
    position = 0

    for _ in range(MAX_SCROLL_STEPS):
        total_height = int(page.evaluate("document.documentElement.scrollHeight"))
        if position >= total_height:
            break
        page.evaluate("value => window.scrollTo({ top: value, behavior: 'instant' })", position)
        page.wait_for_timeout(250)
        positions.append(position)
        position += step
    else:
        raise RuntimeError(
            f"Workbench scrolling exceeded the safety limit of {MAX_SCROLL_STEPS} steps."
        )

    page.evaluate("() => window.scrollTo({ top: 0, behavior: 'instant' })")
    return positions


def _expand_readiness_history(page: Page) -> tuple[bool, int]:
    panels = page.locator("details").filter(has_text="Readiness report history")
    panel_count = panels.count()
    if panel_count < 1:
        return False, panel_count

    panel = panels.first
    panel.scroll_into_view_if_needed(timeout=5_000)
    summary = panel.locator("summary")
    if summary.count() < 1 or not summary.first.is_visible(timeout=2_000):
        return False, panel_count
    if panel.get_attribute("open") is None:
        summary.first.click(timeout=5_000)
        page.wait_for_timeout(300)
    return panel.get_attribute("open") is not None, panel_count


def _write_summary(output_dir: Path, summary: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "playwright-journey.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )


def run(
    output_dir: Path,
    app_url: str = APP_URL,
    api_url: str = API_URL,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots = output_dir / "screenshots"
    screenshots.mkdir(exist_ok=True)

    opportunities = _get_json(f"{api_url.rstrip('/')}/api/opportunities")
    if not isinstance(opportunities, list):
        raise RuntimeError("Opportunity API did not return a list.")
    expected_count = len(opportunities)
    if expected_count < 1:
        raise RuntimeError("Opportunity API returned no opportunities for visual certification.")

    first_title = ""
    if isinstance(opportunities[0], dict):
        first_title = str(opportunities[0].get("title") or "").strip()

    journey: list[dict[str, object]] = []
    console_messages: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on(
                "console",
                lambda message: console_messages.append(f"{message.type}: {message.text}"),
            )
            page.on("pageerror", lambda error: page_errors.append(str(error)))

            page.goto(app_url, wait_until="domcontentloaded", timeout=60_000)
            try:
                _wait_for_loaded_workbench(page, expected_count, first_title)
            except TimeoutError as exc:
                timeout_shot = _screenshot(page, screenshots, "00-load-timeout.png", full_page=True)
                _record(
                    journey,
                    step="wait_for_loaded_workbench",
                    expected="Opportunity data becomes visible within 60 seconds.",
                    actual=f"Timed out waiting for loaded workbench data: {exc}",
                    passed=False,
                    screenshot=timeout_shot,
                )
            else:
                visible_text = page.locator("body").inner_text()
                data_loaded = (
                    f"all ({expected_count})" in visible_text
                    or bool(first_title and first_title in visible_text)
                )
                top = _screenshot(page, screenshots, "01-workbench-top.png")
                _record(
                    journey,
                    step="open_workbench",
                    expected=(
                        "The JOLT workbench renders current opportunity data, not only the shell."
                    ),
                    actual=(
                        f"Rendered data for {expected_count} expected opportunities."
                        if data_loaded
                        else "The shell rendered before opportunity data became visible."
                    ),
                    passed=data_loaded,
                    screenshot=top,
                )

                positions = _scroll_like_reviewer(page)
                full = _screenshot(page, screenshots, "02-workbench-full.png", full_page=True)
                _record(
                    journey,
                    step="review_full_workbench",
                    expected=(
                        "A reviewer can traverse the populated workbench without a page error."
                    ),
                    actual=f"Reviewed {len(positions)} bounded scroll positions.",
                    passed=data_loaded and not page_errors,
                    screenshot=full,
                )

                expanded, panel_count = _expand_readiness_history(page)
                expanded_shot = _screenshot(page, screenshots, "03-readiness-history.png")
                _record(
                    journey,
                    step="expand_readiness_history",
                    expected=(
                        "A populated readiness-history panel can be expanded by its summary control."
                    ),
                    actual=(
                        "Expanded readiness history successfully."
                        if expanded
                        else (
                            "No usable readiness-history panel was available; "
                            f"found {panel_count}."
                        )
                    ),
                    passed=expanded,
                    screenshot=expanded_shot,
                )

                buttons = page.get_by_role("button")
                visible_buttons = sum(
                    1 for index in range(buttons.count()) if buttons.nth(index).is_visible()
                )
                _record(
                    journey,
                    step="inspect_controls",
                    expected=(
                        "Visible interactive controls are discoverable through accessible roles."
                    ),
                    actual=f"Found {visible_buttons} visible buttons.",
                    passed=visible_buttons > 0,
                )
        finally:
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
        "api_url": api_url,
        "expected_opportunity_count": expected_count,
        "result": "failed" if findings else "passed",
        "journey": journey,
        "console_messages": console_messages,
        "page_errors": page_errors,
        "findings": findings,
    }
    _write_summary(output_dir, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the JOLT visual-review Playwright journey.")
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
            "journey": [],
            "console_messages": [],
            "page_errors": [],
            "findings": [{"severity": "error", "message": f"Visual journey crashed: {exc}"}],
        }
        _write_summary(args.output_dir, summary)

    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if summary["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
