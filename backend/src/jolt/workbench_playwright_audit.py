from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, TimeoutError, sync_playwright


def _get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _safe_name(value: str, fallback: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in value)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return (cleaned[:80] or fallback).lower()


def _visible_text(page: Page) -> str:
    return " ".join(page.locator("body").inner_text(timeout=10_000).split())


def _wait_for_workbench(page: Page, first_title: str) -> None:
    page.wait_for_selector("#root", state="attached", timeout=20_000)
    page.wait_for_function(
        "document.body && document.body.innerText.trim().length > 80",
        timeout=30_000,
    )
    if first_title:
        page.get_by_text(first_title, exact=True).first.wait_for(state="visible", timeout=30_000)


def _scroll_like_reviewer(page: Page) -> list[int]:
    heights: list[int] = []
    viewport = page.viewport_size or {"height": 900}
    step = max(400, viewport["height"] - 150)
    total_height = page.evaluate("document.documentElement.scrollHeight")
    position = 0
    while position < total_height:
        page.evaluate("position => window.scrollTo(0, position)", position)
        page.wait_for_timeout(200)
        heights.append(position)
        position += step
        total_height = page.evaluate("document.documentElement.scrollHeight")
    page.evaluate("() => window.scrollTo(0, 0)")
    return heights


def audit_workbench(api_url: str, app_url: str, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    opportunities = _get_json(f"{api_url.rstrip('/')}/api/opportunities")
    if not isinstance(opportunities, list):
        raise ValueError("Opportunity API did not return a list.")

    findings: list[dict[str, str]] = []
    rendered: list[dict[str, object]] = []
    body_text = ""
    scroll_positions: list[int] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        try:
            page.goto(app_url, wait_until="domcontentloaded", timeout=30_000)
            first_title = ""
            if opportunities:
                first_title = str(opportunities[0].get("title") or "").strip()
            _wait_for_workbench(page, first_title)
        except TimeoutError as exc:
            findings.append(
                {
                    "severity": "error",
                    "message": f"Workbench did not render expected content: {exc}",
                }
            )
            page.screenshot(path=output_dir / "workbench-render-timeout.png", full_page=True)
            (output_dir / "workbench-render-timeout.html").write_text(
                page.content(), encoding="utf-8"
            )
        else:
            page.screenshot(path=output_dir / "workbench-top.png", full_page=False)
            scroll_positions = _scroll_like_reviewer(page)
            page.screenshot(path=output_dir / "workbench-full.png", full_page=True)
            body_text = _visible_text(page)
            (output_dir / "workbench-visible-text.txt").write_text(
                body_text, encoding="utf-8"
            )

            for index, opportunity in enumerate(opportunities, start=1):
                title = str(opportunity.get("title") or "").strip()
                company = str(opportunity.get("company") or "").strip()
                location = str(opportunity.get("location") or "").strip()
                posting_id = str(opportunity.get("posting_id") or index)
                title_locator = page.get_by_text(title, exact=True).first if title else None
                title_visible = False
                screenshot = ""

                if title_locator is not None:
                    try:
                        title_visible = title_locator.is_visible(timeout=2_000)
                        if title_visible:
                            title_locator.scroll_into_view_if_needed(timeout=2_000)
                            page.wait_for_timeout(100)
                            screenshot = (
                                f"opportunity-{index:03d}-{_safe_name(title, posting_id)}.png"
                            )
                            page.screenshot(path=output_dir / screenshot, full_page=False)
                    except Exception:
                        title_visible = False

                if not title_visible:
                    findings.append(
                        {
                            "severity": "error",
                            "message": (
                                "Opportunity title is missing from rendered workbench: "
                                f"{title or posting_id}."
                            ),
                        }
                    )

                expected_strategy = {
                    "role_family_id": opportunity.get("role_family_id"),
                    "eligibility": opportunity.get("eligibility"),
                    "fit_now": opportunity.get("fit_now"),
                    "fit_by_interview": opportunity.get("fit_by_interview"),
                    "fit_on_the_job": opportunity.get("fit_on_the_job"),
                    "estimated_preparation_hours": opportunity.get(
                        "estimated_preparation_hours"
                    ),
                }
                rendered.append(
                    {
                        "posting_id": posting_id,
                        "title": title,
                        "company": company,
                        "location": location,
                        "title_visible": title_visible,
                        "company_visible": bool(company and company in body_text),
                        "location_visible": bool(location and location in body_text),
                        "screenshot": screenshot,
                        "api_strategy": expected_strategy,
                    }
                )
        finally:
            browser.close()

    strategy_fields = [
        "role family",
        "eligibility",
        "current fit",
        "interview-ready fit",
        "onboarding fit",
        "preparation",
    ]
    visible_strategy_labels = [label for label in strategy_fields if label in body_text.casefold()]
    if body_text and not visible_strategy_labels and opportunities:
        findings.append(
            {
                "severity": "warning",
                "message": (
                    "The API exposes strategy fields, but the rendered workbench does not "
                    "visibly label them."
                ),
            }
        )

    summary: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "api_url": api_url,
        "app_url": app_url,
        "opportunity_count": len(opportunities),
        "rendered_title_count": sum(bool(item["title_visible"]) for item in rendered),
        "scroll_positions_reviewed": scroll_positions,
        "visible_strategy_labels": visible_strategy_labels,
        "findings": findings,
        "opportunities": rendered,
        "result": "passed" if not any(item["severity"] == "error" for item in findings) else "failed",
    }
    (output_dir / "playwright-calibration-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the real JOLT workbench with Playwright.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--app-url", default="http://127.0.0.1:5173")
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    summary = audit_workbench(arguments.api_url, arguments.app_url, arguments.output_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if summary["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
