from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import BrowserContext, Locator, Page, TimeoutError, sync_playwright

from jolt import multipage_capture
from jolt.supervised_capture import (
    CapturedCard,
    package_run,
    redact_text,
    safe_text,
    wait_for_expected_detail,
)

DEFAULT_SEARCH_URL = multipage_capture.DEFAULT_SEARCH_URL
DEFAULT_API_URL = multipage_capture.DEFAULT_API_URL

_IGNORED_FILTER_LABELS = {
    "following",
    "follow",
    "jobs",
    "my jobs",
    "notifications",
}


@dataclass
class RetryMetrics:
    retry_attempted_count: int = 0
    recovered_after_retry_count: int = 0
    failed_after_retry_count: int = 0


@dataclass(frozen=True)
class CaptureResult:
    cards: list[CapturedCard]
    pages: list[multipage_capture.PageEvidence]
    skipped: list[multipage_capture.SkippedCard]
    stop_reason: str
    search_state: dict[str, Any]
    retry_metrics: RetryMetrics


def _first_input_value(page: Page, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        locator = page.locator(selector)
        try:
            if locator.count() > 0:
                return (locator.first.input_value(timeout=1_000) or "").strip()
        except TimeoutError:
            continue
    return ""


def _normalize_filter_label(value: str) -> str:
    return " ".join(value.split()).strip()


def _is_relevant_filter_label(value: str) -> bool:
    normalized = _normalize_filter_label(value)
    return bool(normalized) and normalized.casefold() not in _IGNORED_FILTER_LABELS


def _active_filter_labels(page: Page) -> list[str]:
    labels: list[str] = []
    selectors = (
        ".search-reusables__filter-pill-button--selected",
        ".search-reusables__filter-pill-button[aria-pressed='true']",
        "button[data-test-reusables-filter-pill-button][aria-pressed='true']",
    )
    for selector in selectors:
        locator = page.locator(selector)
        try:
            count = min(locator.count(), 30)
        except TimeoutError:
            continue
        for index in range(count):
            text = _normalize_filter_label(safe_text(locator.nth(index)))
            if _is_relevant_filter_label(text) and text not in labels:
                labels.append(text)
    return labels


def extract_search_state(page: Page) -> dict[str, Any]:
    effective_url = page.url
    parsed = urlparse(effective_url)
    query = parse_qs(parsed.query)
    keywords = (
        _first_input_value(
            page,
            (
                "input[aria-label*='Search by title' i]",
                "input[placeholder*='Search jobs' i]",
                "input[id*='jobs-search-box-keyword-id']",
            ),
        )
        or query.get("keywords", [""])[0]
    )
    location = (
        _first_input_value(
            page,
            (
                "input[aria-label*='City' i]",
                "input[placeholder*='City' i]",
                "input[id*='jobs-search-box-location-id']",
            ),
        )
        or query.get("location", [""])[0]
    )
    return {
        "effective_url": effective_url,
        "keywords": keywords,
        "location": location,
        "active_filter_labels": _active_filter_labels(page),
        "url_filter_parameters": {
            key: values
            for key, values in query.items()
            if key.startswith("f_") or key in {"geoId", "distance", "sortBy"}
        },
    }


def _click_with_one_retry(
    title_link: Locator,
    card: Locator,
    metrics: RetryMetrics,
) -> bool:
    active_link = title_link
    for attempt in range(2):
        try:
            active_link.click(timeout=8_000)
            if attempt == 1:
                metrics.recovered_after_retry_count += 1
            return True
        except TimeoutError:
            if attempt == 0:
                metrics.retry_attempted_count += 1
                with contextlib.suppress(TimeoutError):
                    card.scroll_into_view_if_needed(timeout=2_000)
                refreshed = multipage_capture._title_link(card)
                if refreshed is not None:
                    active_link = refreshed
    metrics.failed_after_retry_count += 1
    return False


def capture_page_cards(
    page: Page,
    cards: Locator,
    *,
    page_number: int,
    remaining: int,
    evidence_dir: Path,
    seen: set[str],
    skipped: list[multipage_capture.SkippedCard],
    metrics: RetryMetrics,
) -> list[CapturedCard]:
    captured: list[CapturedCard] = []
    try:
        count = cards.count()
    except TimeoutError:
        return captured

    for index in range(count):
        if len(captured) >= remaining:
            break
        card = cards.nth(index)
        with contextlib.suppress(TimeoutError):
            card.scroll_into_view_if_needed(timeout=2_000)

        title_link = multipage_capture._title_link(card)
        source_job_id, source_url = multipage_capture._card_identity(card, title_link)
        if not source_job_id:
            skipped.append(
                multipage_capture.SkippedCard(
                    page_number,
                    index,
                    "",
                    "Card had no usable LinkedIn job identity.",
                )
            )
            continue
        if source_job_id in seen:
            skipped.append(
                multipage_capture.SkippedCard(
                    page_number,
                    index,
                    source_job_id,
                    "Duplicate job identity across pages.",
                )
            )
            continue
        if title_link is None:
            skipped.append(
                multipage_capture.SkippedCard(
                    page_number,
                    index,
                    source_job_id,
                    "Card had no supported title link.",
                )
            )
            continue

        seen.add(source_job_id)
        title = safe_text(title_link)
        company_locator = multipage_capture._first_existing(
            card,
            multipage_capture.COMPANY_SELECTORS,
        )
        location_locator = multipage_capture._first_existing(
            card,
            multipage_capture.LOCATION_SELECTORS,
        )
        company = safe_text(company_locator) if company_locator is not None else ""
        location = safe_text(location_locator) if location_locator is not None else ""

        if not _click_with_one_retry(title_link, card, metrics):
            captured.append(
                CapturedCard(
                    source_job_id,
                    source_url,
                    title,
                    company,
                    location,
                    "",
                    "",
                    False,
                    "Listing click timed out after one retry.",
                )
            )
            continue

        verified = wait_for_expected_detail(page, source_job_id)
        detail_html = page.content() if verified else ""
        description = multipage_capture._detail_description(page) if verified else ""
        reason = (
            "" if verified else "Detail panel did not reach the expected LinkedIn job identity."
        )
        with contextlib.suppress(Exception):
            page.screenshot(
                path=evidence_dir / f"page_{page_number}_job_{source_job_id}.png",
                full_page=False,
            )
        captured.append(
            CapturedCard(
                source_job_id,
                source_url,
                title,
                company,
                location,
                detail_html,
                description,
                verified,
                reason,
            )
        )
    return captured


def capture_pages(
    page: Page,
    *,
    max_jobs: int,
    max_pages: int,
    evidence_dir: Path,
    metrics: RetryMetrics,
) -> tuple[
    list[CapturedCard],
    list[multipage_capture.PageEvidence],
    list[multipage_capture.SkippedCard],
    str,
]:
    captured: list[CapturedCard] = []
    pages: list[multipage_capture.PageEvidence] = []
    skipped: list[multipage_capture.SkippedCard] = []
    seen: set[str] = set()
    cards, selector = multipage_capture._wait_for_cards(page)
    stop_reason = "max_pages_reached"

    for page_number in range(1, max_pages + 1):
        visible_ids = multipage_capture._visible_job_ids(cards)
        control, next_present, next_enabled = multipage_capture._next_control(
            page,
            page_number + 1,
        )
        pages.append(
            multipage_capture.PageEvidence(
                page_number=page_number,
                visible_job_ids=visible_ids,
                matched_card_selector=selector,
                next_control_present=next_present,
                next_control_enabled=next_enabled,
            )
        )
        with contextlib.suppress(Exception):
            page.screenshot(
                path=evidence_dir / f"page_{page_number}_listing.png",
                full_page=False,
            )

        captured.extend(
            capture_page_cards(
                page,
                cards,
                page_number=page_number,
                remaining=max_jobs - len(captured),
                evidence_dir=evidence_dir,
                seen=seen,
                skipped=skipped,
                metrics=metrics,
            )
        )
        if len(captured) >= max_jobs:
            stop_reason = "requested_limit_reached"
            break
        if page_number >= max_pages:
            stop_reason = "max_pages_reached"
            break
        if control is None or not next_present:
            stop_reason = "no_next_page"
            break
        if not next_enabled:
            stop_reason = "next_page_disabled"
            break

        advanced = multipage_capture._advance_page(page, control, visible_ids)
        if advanced is None:
            stop_reason = "next_page_failed"
            break
        cards, selector = advanced
    return captured, pages, skipped, stop_reason


def build_submit_payload(
    cards: list[CapturedCard],
    pages: list[multipage_capture.PageEvidence],
    search_url: str,
    requested_item_limit: int,
    stop_reason: str,
) -> dict[str, Any]:
    return {
        "search_url": search_url,
        "requested_item_limit": requested_item_limit,
        "stop_reason": stop_reason,
        "pages": [
            {
                "page_number": page.page_number,
                "visible_job_ids": list(page.visible_job_ids),
                "next_control_present": page.next_control_present,
                "next_control_enabled": page.next_control_enabled,
            }
            for page in pages
        ],
        "items": [
            {
                "source_job_id": card.source_job_id,
                "source_url": card.source_url,
                "title": card.title,
                "company": card.company,
                "location": card.location,
                "description": card.description,
                "identity_verified": card.identity_verified,
                "verification_reason": card.verification_reason,
            }
            for card in cards
        ],
    }


def submit_capture(
    api_url: str,
    cards: list[CapturedCard],
    pages: list[multipage_capture.PageEvidence],
    search_url: str,
    requested_item_limit: int,
    stop_reason: str,
) -> dict[str, Any]:
    payload = json.dumps(
        build_submit_payload(
            cards,
            pages,
            search_url,
            requested_item_limit,
            stop_reason,
        )
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/captures/linkedin/live",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"submitted": False, "error": str(exc)}


def _write_failure_diagnostics(
    staging_dir: Path,
    evidence_dir: Path,
    page: Page | None,
    error: Exception,
) -> None:
    (staging_dir / "failure.json").write_text(
        json.dumps(
            {
                "captured_at": datetime.now(UTC).isoformat(),
                "error_type": type(error).__name__,
                "error": str(error),
                "supported_card_selectors": multipage_capture.CARD_SELECTORS,
                "supported_next_selectors": multipage_capture.NEXT_CONTROL_SELECTORS,
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    if page is not None:
        with contextlib.suppress(Exception):
            page.screenshot(path=evidence_dir / "failure_page.png", full_page=True)
            (staging_dir / "failure_page.redacted.html").write_text(
                redact_text(page.content()),
                encoding="utf-8",
            )


def run_capture(
    search_url: str,
    api_url: str,
    profile_dir: Path,
    output_zip: Path,
    max_jobs: int,
    max_pages: int,
    pause_for_login: bool,
) -> Path:
    staging_dir = Path(tempfile.mkdtemp(prefix="jolt_linkedin_"))
    evidence_dir = staging_dir / "evidence"
    evidence_dir.mkdir(parents=True)
    page: Page | None = None
    context: BrowserContext | None = None
    metrics = RetryMetrics()

    try:
        try:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    headless=False,
                    viewport={"width": 1440, "height": 1000},
                )
                context.tracing.start(screenshots=True, snapshots=True, sources=False)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
                page.screenshot(
                    path=evidence_dir / "01_search_opened.png",
                    full_page=False,
                )

                if pause_for_login:
                    print("LinkedIn is open in a persistent local browser profile.")
                    print(
                        "Log in manually if needed, apply the desired search filters, "
                        "then return here."
                    )
                    input("Press Enter to start the bounded capture: ")

                search_state = extract_search_state(page)
                search_url = page.url
                cards, pages, skipped, stop_reason = capture_pages(
                    page,
                    max_jobs=max_jobs,
                    max_pages=max_pages,
                    evidence_dir=evidence_dir,
                    metrics=metrics,
                )
                if not cards:
                    raise RuntimeError("No usable LinkedIn job cards were captured.")
                page.screenshot(
                    path=evidence_dir / "99_capture_complete.png",
                    full_page=False,
                )
                context.tracing.stop(path=evidence_dir / "playwright_trace.zip")
                context.close()
                context = None

            summary = {
                "search_url": search_url,
                "captured_at": datetime.now(UTC).isoformat(),
                "max_jobs": max_jobs,
                "max_pages": max_pages,
                "captured_count": len(cards),
                "verified_count": sum(card.identity_verified for card in cards),
                "stop_reason": stop_reason,
                "search_state": search_state,
                "retry_metrics": asdict(metrics),
                "pages": [asdict(item) for item in pages],
                "skipped_cards": [asdict(item) for item in skipped],
                "cards": [
                    asdict(card)
                    | {
                        "detail_html": "[stored separately]",
                        "description": "[submitted]",
                    }
                    for card in cards
                ],
            }
            (staging_dir / "capture_summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
            for card in cards:
                if card.detail_html:
                    (evidence_dir / f"job_{card.source_job_id}.redacted.html").write_text(
                        redact_text(card.detail_html),
                        encoding="utf-8",
                    )

            api_result = submit_capture(
                api_url,
                cards,
                pages,
                search_url,
                requested_item_limit=max_jobs,
                stop_reason=stop_reason,
            )
            (staging_dir / "api_result.json").write_text(
                json.dumps(api_result, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
            (staging_dir / "run.log").write_text(
                redact_text(
                    "\n".join(
                        [
                            f"Captured {len(cards)} jobs across {len(pages)} page(s).",
                            f"Verified {sum(card.identity_verified for card in cards)} detail panels.",
                            f"Skipped {len(skipped)} unsupported or duplicate cards.",
                            f"Stop reason: {stop_reason}",
                            f"Retry attempts: {metrics.retry_attempted_count}",
                            f"Recovered after retry: {metrics.recovered_after_retry_count}",
                            f"Failed after retry: {metrics.failed_after_retry_count}",
                            "API result: "
                            f"{api_result.get('status', api_result.get('error', 'completed'))}",
                        ]
                    )
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            _write_failure_diagnostics(staging_dir, evidence_dir, page, exc)
            if context is not None:
                with contextlib.suppress(Exception):
                    context.tracing.stop(path=evidence_dir / "playwright_trace.zip")
                with contextlib.suppress(Exception):
                    context.close()
            package_run(staging_dir, output_zip)
            raise

        return package_run(staging_dir, output_zip)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a bounded multi-page LinkedIn capture.")
    parser.add_argument("--search-url", default=DEFAULT_SEARCH_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--max-jobs", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--no-login-pause", action="store_true")
    args = parser.parse_args(argv)
    if args.max_jobs < 1 or args.max_jobs > 50:
        parser.error("--max-jobs must be between 1 and 50.")
    if args.max_pages < 1 or args.max_pages > 10:
        parser.error("--max-pages must be between 1 and 10.")
    return args


def main() -> int:
    args = parse_args(sys.argv[1:])
    output = run_capture(
        search_url=args.search_url,
        api_url=args.api_url,
        profile_dir=args.profile_dir,
        output_zip=args.output_zip,
        max_jobs=args.max_jobs,
        max_pages=args.max_pages,
        pause_for_login=not args.no_login_pause,
    )
    print(f"Capture package created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
