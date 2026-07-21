from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

APP_URL = "http://127.0.0.1:5173"
API_URL = "http://127.0.0.1:8000"
VIEWPORT = {"width": 1440, "height": 1000}


def _progress(message: str) -> None:
    print(f"[opportunity-audit] {message}", flush=True)


def _get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _capture(page: Page, path: Path, *, full_page: bool = True) -> None:
    _progress(f"Capturing {path.name}.")
    page.screenshot(path=path, full_page=full_page, animations="disabled", timeout=60_000)


def _body_contains(page: Page, text: str, timeout: int = 60_000) -> None:
    page.wait_for_function(
        "expected => (document.body?.innerText || '').includes(expected)",
        arg=text,
        timeout=timeout,
    )


def _document_metrics(page: Page) -> dict[str, int | bool]:
    return page.evaluate(
        """
        () => ({
          viewportWidth: window.innerWidth,
          viewportHeight: window.innerHeight,
          documentWidth: document.documentElement.scrollWidth,
          documentHeight: document.documentElement.scrollHeight,
          horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        })
        """
    )


def run(output_dir: Path, app_url: str = APP_URL, api_url: str = API_URL) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots = output_dir / "screenshots"
    screenshots.mkdir(exist_ok=True)

    _progress("Loading populated opportunity data.")
    raw_opportunities = _get_json(f"{api_url.rstrip('/')}/api/opportunities")
    if not isinstance(raw_opportunities, list) or not raw_opportunities:
        raise RuntimeError("Opportunity audit requires a populated opportunity dataset.")
    opportunities = [item for item in raw_opportunities if isinstance(item, dict)]
    if not opportunities:
        raise RuntimeError("Opportunity API returned no usable opportunity objects.")

    first = opportunities[0]
    search_term = str(first.get("company") or first.get("title") or "").strip()
    if not search_term:
        raise RuntimeError("The first opportunity has no title or company for search validation.")
    expected_search_count = sum(
        search_term.casefold()
        in " ".join(
            str(item.get(field) or "") for field in ("title", "company", "location")
        ).casefold()
        for item in opportunities
    )
    expected_title = min(
        (str(item.get("title") or "Untitled opportunity") for item in opportunities),
        key=str.casefold,
    )

    findings: list[dict[str, str]] = []
    console_messages: list[str] = []
    page_errors: list[str] = []
    journey: dict[str, Any] = {
        "search_term": search_term,
        "expected_search_count": expected_search_count,
        "expected_first_title_after_sort": expected_title,
    }

    with sync_playwright() as playwright:
        _progress("Launching Playwright Chromium.")
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport=VIEWPORT)
            page.set_default_timeout(30_000)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "console",
                lambda message: console_messages.append(f"{message.type}: {message.text}"),
            )

            _progress(f"Opening {app_url}.")
            page.goto(app_url, wait_until="domcontentloaded", timeout=60_000)
            page.get_by_role("navigation", name="JOLT workspace views").wait_for(
                state="visible", timeout=30_000
            )
            _body_contains(page, f"all ({len(opportunities)})")
            page.get_by_role("button", name="Opportunities", exact=True).click()
            page.get_by_role("heading", name="Opportunity review workbench", exact=True).wait_for(
                state="visible"
            )
            page.get_by_label("Search opportunities").wait_for(state="visible")
            page.get_by_label("Sort").wait_for(state="visible")

            default_metrics = _document_metrics(page)
            journey["default"] = default_metrics
            if default_metrics["horizontalOverflow"]:
                findings.append(
                    {"severity": "error", "message": "Default queue has horizontal overflow."}
                )
            _capture(page, screenshots / "01-default-queue.png")

            _progress(f"Searching for {search_term!r}.")
            search = page.get_by_label("Search opportunities")
            search.fill(search_term)
            expected_summary = f"of {expected_search_count}"
            _body_contains(page, expected_summary)
            visible_rows = page.locator(".opportunity-row").count()
            journey["search"] = {
                "visible_rows": visible_rows,
                "summary_fragment": expected_summary,
            }
            if visible_rows != min(expected_search_count, 20):
                findings.append(
                    {
                        "severity": "error",
                        "message": (
                            "Search row count does not match the expected first-page result count: "
                            f"expected {min(expected_search_count, 20)}, found {visible_rows}."
                        ),
                    }
                )
            _capture(page, screenshots / "02-search-results.png")

            _progress("Validating title sorting.")
            search.fill("")
            page.get_by_label("Sort").select_option("title_asc")
            first_heading = page.locator(".opportunity-row h3").first
            first_heading.wait_for(state="visible")
            actual_first_title = first_heading.inner_text().strip()
            journey["sort"] = {"actual_first_title": actual_first_title}
            if actual_first_title != expected_title:
                findings.append(
                    {
                        "severity": "error",
                        "message": (
                            f"Title sorting expected {expected_title!r} first but found "
                            f"{actual_first_title!r}."
                        ),
                    }
                )
            _capture(page, screenshots / "03-title-sort.png")

            _progress("Opening the opportunity inspector.")
            page.get_by_role("button", name="Inspect", exact=True).first.click()
            dialog = page.get_by_role("dialog")
            dialog.wait_for(state="visible")
            dialog_box = dialog.bounding_box()
            close_button = dialog.get_by_role("button", name="Close", exact=True)
            source_link_visible = dialog.get_by_role("link", name="Open source job").is_visible()
            preparation_link_visible = dialog.get_by_role(
                "link", name="Download preparation pack"
            ).is_visible()
            automated_review_visible = dialog.get_by_text(
                "Automated proposed decision", exact=True
            ).is_visible()
            journey["inspector"] = {
                "bounding_box": dialog_box,
                "source_link_visible": source_link_visible,
                "preparation_link_visible": preparation_link_visible,
                "automated_review_visible": automated_review_visible,
                "close_button_focused": close_button.evaluate(
                    "element => element === document.activeElement"
                ),
            }
            if dialog_box is None:
                findings.append(
                    {"severity": "error", "message": "Inspector has no measurable bounding box."}
                )
            else:
                if dialog_box["width"] < 420:
                    findings.append(
                        {"severity": "warning", "message": "Inspector is narrower than 420px."}
                    )
                if dialog_box["width"] > VIEWPORT["width"]:
                    findings.append(
                        {"severity": "error", "message": "Inspector exceeds viewport width."}
                    )
            for visible, label in (
                (source_link_visible, "source link"),
                (preparation_link_visible, "preparation-pack link"),
                (automated_review_visible, "automated review"),
            ):
                if not visible:
                    findings.append(
                        {"severity": "error", "message": f"Inspector is missing visible {label}."}
                    )
            _capture(page, screenshots / "04-opportunity-inspector.png", full_page=False)

            _progress("Validating Escape-key close behavior.")
            page.keyboard.press("Escape")
            try:
                dialog.wait_for(state="hidden", timeout=2_000)
                escape_closed = True
            except Exception:  # noqa: BLE001
                escape_closed = False
                findings.append(
                    {
                        "severity": "error",
                        "message": "Escape did not close the modal opportunity inspector.",
                    }
                )
                close_button.click()
            journey["inspector"]["escape_closed"] = escape_closed
        finally:
            _progress("Closing Playwright Chromium.")
            browser.close()

    findings.extend(
        {"severity": "error", "message": f"Browser page error: {error}"} for error in page_errors
    )
    has_errors = any(item["severity"] == "error" for item in findings)
    summary: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "app_url": app_url,
        "api_url": api_url,
        "viewport": VIEWPORT,
        "result": "failed" if has_errors else "passed",
        "opportunity_count": len(opportunities),
        "journey": journey,
        "screenshots": [
            "screenshots/01-default-queue.png",
            "screenshots/02-search-results.png",
            "screenshots/03-title-sort.png",
            "screenshots/04-opportunity-inspector.png",
        ],
        "console_messages": console_messages,
        "page_errors": page_errors,
        "findings": findings,
    }
    summary_path = output_dir / "opportunity-experience-audit.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _progress(f"Audit summary written to {summary_path}.")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit JOLT opportunity search, sorting, and inspector UX."
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--app-url", default=APP_URL)
    parser.add_argument("--api-url", default=API_URL)
    args = parser.parse_args()

    try:
        summary = run(args.output_dir, args.app_url, args.api_url)
    except Exception as exc:  # noqa: BLE001
        _progress(f"FAILED: {exc}")
        summary = {
            "generated_at": datetime.now(UTC).isoformat(),
            "app_url": args.app_url,
            "api_url": args.api_url,
            "result": "failed",
            "findings": [
                {"severity": "error", "message": f"Opportunity experience audit crashed: {exc}"}
            ],
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "opportunity-experience-audit.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

    print(json.dumps(summary, indent=2), flush=True)
    return 0 if summary["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
