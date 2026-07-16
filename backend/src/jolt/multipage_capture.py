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

from playwright.sync_api import BrowserContext, Locator, Page, TimeoutError, sync_playwright

from jolt.supervised_capture import (
    COMPANY_SELECTORS,
    DETAIL_SELECTORS,
    LOCATION_SELECTORS,
    TITLE_LINK_SELECTORS,
    CapturedCard,
    extract_job_id,
    package_run,
    redact_text,
    safe_text,
    wait_for_expected_detail,
)

DEFAULT_SEARCH_URL = "https://www.linkedin.com/jobs/search/"
DEFAULT_API_URL = "http://127.0.0.1:8000"
CARD_SELECTORS = (
    ".jobs-search-results__list-item",
    "li[data-occludable-job-id]",
    "[data-job-id].job-card-container",
    "[data-job-id][class*='job-card']",
)
NEXT_CONTROL_SELECTORS = (
    ".jobs-search-pagination__button--next",
    "button[aria-label='View next page']",
    "button[aria-label='Next']",
    "button[aria-label*='next' i]",
)


@dataclass(frozen=True)
class PageEvidence:
    page_number: int
    visible_job_ids: tuple[str, ...]
    matched_card_selector: str
    next_control_present: bool
    next_control_enabled: bool


@dataclass(frozen=True)
class SkippedCard:
    page_number: int
    card_index: int
    source_job_id: str
    reason: str


def _safe_attribute(locator: Locator | None, name: str) -> str:
    if locator is None:
        return ""
    try:
        return locator.get_attribute(name, timeout=2_000) or ""
    except TimeoutError:
        return ""


def _first_existing(root: Page | Locator, selectors: tuple[str, ...]) -> Locator | None:
    for selector in selectors:
        locator = root.locator(selector)
        try:
            if locator.count() > 0:
                return locator.first
        except TimeoutError:
            continue
    return None


def _select_cards(page: Page) -> tuple[Locator | None, str]:
    for selector in CARD_SELECTORS:
        locator = page.locator(selector)
        try:
            if locator.count() > 0:
                return locator, selector
        except TimeoutError:
            continue
    return None, ""


def _wait_for_cards(page: Page, timeout_ms: int = 60_000) -> tuple[Locator, str]:
    deadline = datetime.now(UTC).timestamp() + timeout_ms / 1000
    while datetime.now(UTC).timestamp() < deadline:
        cards, selector = _select_cards(page)
        if cards is not None and selector:
            return cards, selector
        page.wait_for_timeout(750)
    raise TimeoutError("No supported LinkedIn job-card layout was detected.")


def _title_link(card: Locator) -> Locator | None:
    return _first_existing(card, TITLE_LINK_SELECTORS)


def _card_identity(card: Locator, title_link: Locator | None = None) -> tuple[str, str]:
    source_job_id = _safe_attribute(card, "data-job-id") or _safe_attribute(
        card, "data-occludable-job-id"
    )
    link = title_link or _title_link(card)
    source_url = _safe_attribute(link, "href")
    return source_job_id or extract_job_id(source_url), source_url


def _visible_job_ids(cards: Locator) -> tuple[str, ...]:
    visible: list[str] = []
    try:
        count = cards.count()
    except TimeoutError:
        return ()
    for index in range(count):
        try:
            source_job_id, _ = _card_identity(cards.nth(index))
        except TimeoutError:
            continue
        if source_job_id and source_job_id not in visible:
            visible.append(source_job_id)
    return tuple(visible)


def _detail_description(page: Page) -> str:
    for selector in DETAIL_SELECTORS:
        locator = page.locator(selector)
        try:
            if locator.count() == 0:
                continue
        except TimeoutError:
            continue
        text = safe_text(locator.first)
        if len(text) >= 40:
            return text
    return ""


def capture_page_cards(
    page: Page,
    cards: Locator,
    *,
    page_number: int,
    remaining: int,
    evidence_dir: Path,
    seen: set[str],
    skipped: list[SkippedCard],
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
        try:
            card.scroll_into_view_if_needed(timeout=2_000)
        except TimeoutError:
            pass

        title_link = _title_link(card)
        source_job_id, source_url = _card_identity(card, title_link)
        if not source_job_id:
            skipped.append(
                SkippedCard(page_number, index, "", "Card had no usable LinkedIn job identity.")
            )
            continue
        if source_job_id in seen:
            skipped.append(
                SkippedCard(page_number, index, source_job_id, "Duplicate job identity across pages.")
            )
            continue
        if title_link is None:
            skipped.append(
                SkippedCard(page_number, index, source_job_id, "Card had no supported title link.")
            )
            continue

        seen.add(source_job_id)
        title = safe_text(title_link)
        company_locator = _first_existing(card, COMPANY_SELECTORS)
        location_locator = _first_existing(card, LOCATION_SELECTORS)
        company = safe_text(company_locator) if company_locator is not None else ""
        location = safe_text(location_locator) if location_locator is not None else ""

        try:
            title_link.click(timeout=8_000)
        except TimeoutError:
            captured.append(
                CapturedCard(
                    source_job_id=source_job_id,
                    source_url=source_url,
                    title=title,
                    company=company,
                    location=location,
                    detail_html="",
                    description="",
                    identity_verified=False,
                    verification_reason="Listing click timed out.",
                )
            )
            continue

        verified = wait_for_expected_detail(page, source_job_id)
        detail_html = page.content() if verified else ""
        description = _detail_description(page) if verified else ""
        reason = "" if verified else "Detail panel did not reach the expected LinkedIn job identity."
        with contextlib.suppress(Exception):
            page.screenshot(
                path=evidence_dir / f"page_{page_number}_job_{source_job_id}.png",
                full_page=False,
            )
        captured.append(
            CapturedCard(
                source_job_id=source_job_id,
                source_url=source_url,
                title=title,
                company=company,
                location=location,
                detail_html=detail_html,
                description=description,
                identity_verified=verified,
                verification_reason=reason,
            )
        )
    return captured


def _numbered_page_control(page: Page, next_page_number: int) -> Locator | None:
    selectors = (
        f"button[aria-label='Page {next_page_number}']",
        f"button[data-test-pagination-page-btn='{next_page_number}']",
    )
    direct = _first_existing(page, selectors)
    if direct is not None:
        return direct

    pagination = page.locator(".artdeco-pagination, .jobs-search-pagination")
    try:
        if pagination.count() == 0:
            return None
    except TimeoutError:
        return None
    buttons = pagination.first.locator("button").filter(has_text=str(next_page_number))
    try:
        return buttons.first if buttons.count() > 0 else None
    except TimeoutError:
        return None


def _next_control(page: Page, next_page_number: int) -> tuple[Locator | None, bool, bool]:
    control = _numbered_page_control(page, next_page_number)
    if control is None:
        control = _first_existing(page, NEXT_CONTROL_SELECTORS)
    if control is None:
        return None, False, False
    try:
        visible = control.is_visible(timeout=1_000)
        enabled = control.is_enabled(timeout=1_000)
    except TimeoutError:
        return control, True, False
    return control, visible, visible and enabled


def _advance_page(
    page: Page,
    control: Locator,
    previous_ids: tuple[str, ...],
    timeout_ms: int = 20_000,
) -> tuple[Locator, str] | None:
    try:
        control.click(timeout=8_000)
    except TimeoutError:
        return None

    deadline = datetime.now(UTC).timestamp() + timeout_ms / 1000
    while datetime.now(UTC).timestamp() < deadline:
        page.wait_for_timeout(750)
        cards, selector = _select_cards(page)
        if cards is None:
            continue
        current_ids = _visible_job_ids(cards)
        if current_ids and current_ids != previous_ids:
            return cards, selector
    return None


def capture_pages(
    page: Page,
    *,
    max_jobs: int,
    max_pages: int,
    evidence_dir: Path,
) -> tuple[list[CapturedCard], list[PageEvidence], list[SkippedCard], str]:
    captured: list[CapturedCard] = []
    pages: list[PageEvidence] = []
    skipped: list[SkippedCard] = []
    seen: set[str] = set()
    cards, selector = _wait_for_cards(page)
    stop_reason = "max_pages_reached"

    for page_number in range(1, max_pages + 1):
        visible_ids = _visible_job_ids(cards)
        control, next_present, next_enabled = _next_control(page, page_number + 1)
        pages.append(
            PageEvidence(
                page_number=page_number,
                visible_job_ids=visible_ids,
                matched_card_selector=selector,
                next_control_present=next_present,
                next_control_enabled=next_enabled,
            )
        )
        with contextlib.suppress(Exception):
            page.screenshot(
                path=evidence_dir / f"page_{page_number}_listing.png", full_page=False
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

        advanced = _advance_page(page, control, visible_ids)
        if advanced is None:
            stop_reason = "next_page_failed"
            break
        cards, selector = advanced
    return captured, pages, skipped, stop_reason


def submit_capture(
    api_url: str,
    cards: list[CapturedCard],
    search_url: str,
    requested_item_limit: int,
    stop_reason: str,
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "search_url": search_url,
            "requested_item_limit": requested_item_limit,
            "stop_reason": stop_reason,
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
    staging_dir: Path, evidence_dir: Path, page: Page | None, error: Exception
) -> None:
    (staging_dir / "failure.json").write_text(
        json.dumps(
            {
                "captured_at": datetime.now(UTC).isoformat(),
                "error_type": type(error).__name__,
                "error": str(error),
                "supported_card_selectors": CARD_SELECTORS,
                "supported_next_selectors": NEXT_CONTROL_SELECTORS,
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
                redact_text(page.content()), encoding="utf-8"
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
                page.screenshot(path=evidence_dir / "01_search_opened.png", full_page=False)

                if pause_for_login:
                    print("LinkedIn is open in a persistent local browser profile.")
                    print(
                        "Log in manually if needed, apply the desired search filters, then return here."
                    )
                    input("Press Enter to start the bounded capture: ")

                search_url = page.url
                cards, pages, skipped, stop_reason = capture_pages(
                    page,
                    max_jobs=max_jobs,
                    max_pages=max_pages,
                    evidence_dir=evidence_dir,
                )
                if not cards:
                    raise RuntimeError("No usable LinkedIn job cards were captured.")
                page.screenshot(path=evidence_dir / "99_capture_complete.png", full_page=False)
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
                "pages": [asdict(item) for item in pages],
                "skipped_cards": [asdict(item) for item in skipped],
                "cards": [
                    asdict(card)
                    | {"detail_html": "[stored separately]", "description": "[submitted]"}
                    for card in cards
                ],
            }
            (staging_dir / "capture_summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
            )
            for card in cards:
                if card.detail_html:
                    (evidence_dir / f"job_{card.source_job_id}.redacted.html").write_text(
                        redact_text(card.detail_html), encoding="utf-8"
                    )

            api_result = submit_capture(
                api_url,
                cards,
                search_url,
                requested_item_limit=max_jobs,
                stop_reason=stop_reason,
            )
            (staging_dir / "api_result.json").write_text(
                json.dumps(api_result, indent=2, ensure_ascii=True), encoding="utf-8"
            )
            (staging_dir / "run.log").write_text(
                redact_text(
                    "\n".join(
                        [
                            f"Captured {len(cards)} jobs across {len(pages)} page(s).",
                            f"Verified {sum(card.identity_verified for card in cards)} detail panels.",
                            f"Skipped {len(skipped)} unsupported or duplicate cards.",
                            f"Stop reason: {stop_reason}",
                            f"API result: {api_result.get('status', api_result.get('error', 'completed'))}",
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
