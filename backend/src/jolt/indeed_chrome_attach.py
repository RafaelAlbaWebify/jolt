from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import playwright.sync_api as playwright_sync_api
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from jolt.indeed_capture import (
    _access_warning,
    _click_listing_candidate,
    _detail_fields,
    _visible_listing_candidates,
    _wait_for_detail_panel,
    canonical_indeed_job_url,
    submit_capture,
)
from jolt.supervised_capture import CapturedCard, package_run, redact_text


def _select_indeed_page(browser: Browser) -> tuple[BrowserContext, Page]:
    contexts = browser.contexts
    if not contexts:
        raise RuntimeError("Chrome exposed no browser context over CDP.")

    candidates: list[tuple[BrowserContext, Page]] = []
    for context in contexts:
        for page in context.pages:
            url = (page.url or "").casefold()
            if "indeed." in url and "/jobs" in url:
                return context, page
            if "indeed." in url:
                candidates.append((context, page))

    if candidates:
        return candidates[0]
    raise RuntimeError(
        "No Indeed tab was found in the attached Chrome instance. "
        "Open an Indeed jobs search in that Chrome window and retry."
    )


def _navigate_search_page(
    context: BrowserContext,
    page: Page,
    target_url: str,
) -> Page:
    if page.is_closed():
        page = context.new_page()

    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=60_000)
        return page
    except playwright_sync_api.Error as exc:
        if "closed" not in str(exc).casefold():
            raise
        replacement = context.new_page()
        replacement.goto(target_url, wait_until="domcontentloaded", timeout=60_000)
        return replacement


def _page_search_url(search_url: str, page_number: int) -> str:
    parsed = urlparse(search_url)
    pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {"start", "vjk", "jk"}
    ]
    if page_number > 1:
        pairs.append(("start", str((page_number - 1) * 10)))
    return urlunparse(parsed._replace(query=urlencode(pairs, doseq=True)))


def _wait_for_visible_results(
    page: Page,
    max_jobs: int,
    *,
    timeout_ms: int = 180_000,
) -> list[dict[str, str]]:
    elapsed = 0
    announced_verification = False
    while elapsed < timeout_ms:
        candidates = _visible_listing_candidates(page, max_jobs)
        if candidates:
            return candidates

        warning = _access_warning(page)
        if warning and not announced_verification:
            print("Indeed verification is visible. Complete it manually in Chrome.")
            print("JOLT will continue automatically when job results become available.")
            announced_verification = True

        page.wait_for_timeout(500)
        elapsed += 500

    raise RuntimeError(
        "Timed out waiting for visible Indeed job results in the attached Chrome tab."
    )


def run_capture(
    *,
    cdp_endpoint: str,
    api_url: str,
    output_zip: Path,
    max_jobs: int,
    max_pages: int,
    pause_before_capture: bool,
) -> Path:
    staging_dir = Path(tempfile.mkdtemp(prefix="jolt_indeed_cdp_"))
    evidence_dir = staging_dir / "evidence"
    evidence_dir.mkdir(parents=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(cdp_endpoint, timeout=30_000)
            context, attached_page = _select_indeed_page(browser)

            with contextlib.suppress(Exception):
                attached_page.screenshot(
                    path=evidence_dir / "01_attached_search.png",
                    full_page=False,
                )

            print("JOLT is attached to Google Chrome.")
            print("Waiting for visible Indeed job results...")
            _wait_for_visible_results(attached_page, 1)

            base_search_url = _page_search_url(attached_page.url, 1)
            page = _navigate_search_page(context, attached_page, base_search_url)
            cards: list[CapturedCard] = []
            pages: list[dict[str, object]] = []
            seen_job_ids: set[str] = set()
            result_position = 0
            exhausted = False

            for page_number in range(1, max_pages + 1):
                if len(cards) >= max_jobs:
                    break

                target_url = _page_search_url(base_search_url, page_number)
                if page_number > 1:
                    print(f"Opening Indeed results page {page_number}: {target_url}")
                page = _navigate_search_page(context, page, target_url)

                candidates = _wait_for_visible_results(page, 15)
                visible_ids = [candidate["source_job_id"] for candidate in candidates]
                pages.append(
                    {
                        "page_number": page_number,
                        "visible_job_ids": visible_ids,
                    }
                )

                new_candidates = [
                    candidate
                    for candidate in candidates
                    if candidate["source_job_id"] not in seen_job_ids
                ]
                if pause_before_capture:
                    print(
                        f"Page {page_number}: {len(candidates)} visible, "
                        f"{len(new_candidates)} new after jk deduplication."
                    )

                if not new_candidates:
                    exhausted = True
                    break

                for card_index, candidate in enumerate(new_candidates):
                    if len(cards) >= max_jobs:
                        break

                    source_job_id = candidate["source_job_id"]
                    source_url = candidate["source_url"]
                    title_hint = candidate["title"]
                    seen_job_ids.add(source_job_id)
                    result_position += 1

                    if page.is_closed():
                        page = _navigate_search_page(context, page, target_url)

                    clicked = _click_listing_candidate(page, source_job_id)
                    if not clicked and page.is_closed():
                        page = _navigate_search_page(context, page, target_url)
                        clicked = _click_listing_candidate(page, source_job_id)

                    if not clicked:
                        cards.append(
                            CapturedCard(
                                source_job_id,
                                source_url,
                                title_hint,
                                "",
                                "",
                                "",
                                "",
                                False,
                                "Indeed listing card could not be clicked in attached Chrome.",
                                result_position=result_position,
                                page_number=page_number,
                                card_index=card_index,
                            )
                        )
                        continue

                    warning = _access_warning(page)
                    if warning:
                        raise RuntimeError(warning)

                    panel_ready = _wait_for_detail_panel(page, source_job_id, title_hint)
                    title, company, location, description, verified, reason = _detail_fields(
                        page, source_job_id, title_hint
                    )
                    if not panel_ready and verified:
                        verified = False
                        reason = (
                            "Indeed detail panel did not become stable after the listing click."
                        )

                    detail_html = page.content() if verified else ""
                    with contextlib.suppress(Exception):
                        page.screenshot(
                            path=evidence_dir / f"p{page_number:02d}_job_{source_job_id}.png",
                            full_page=False,
                            timeout=5_000,
                        )

                    cards.append(
                        CapturedCard(
                            source_job_id,
                            canonical_indeed_job_url(source_url),
                            title,
                            company,
                            location,
                            detail_html,
                            description,
                            verified,
                            reason,
                            result_position=result_position,
                            page_number=page_number,
                            card_index=card_index,
                        )
                    )

            stop_reason = (
                "requested_limit_reached"
                if len(cards) >= max_jobs
                else "results_exhausted"
                if exhausted
                else "page_limit_reached"
            )

            summary = {
                "source": "indeed",
                "mode": "chrome_cdp_attach_multipage",
                "cdp_endpoint": cdp_endpoint,
                "search_url": base_search_url,
                "captured_at": datetime.now(UTC).isoformat(),
                "max_jobs": max_jobs,
                "max_pages": max_pages,
                "pages_visited": len(pages),
                "captured_count": len(cards),
                "verified_count": sum(card.identity_verified for card in cards),
                "stop_reason": stop_reason,
                "pages": pages,
                "cards": [
                    asdict(card)
                    | {"detail_html": "[stored separately]", "description": "[submitted]"}
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

            api_result = submit_capture(api_url, cards, base_search_url, max_jobs, pages)
            (staging_dir / "api_result.json").write_text(
                json.dumps(api_result, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
            (staging_dir / "run.log").write_text(
                redact_text(
                    "\n".join(
                        [
                            "Mode: attached Google Chrome over CDP, multi-page.",
                            f"Visited {len(pages)} Indeed result pages.",
                            f"Captured {len(cards)} unique Indeed jobs.",
                            f"Verified {sum(card.identity_verified for card in cards)} detail panels.",
                            f"API result: {api_result.get('status', api_result.get('error', 'completed'))}",
                        ]
                    )
                ),
                encoding="utf-8",
            )

        return package_run(staging_dir, output_zip)
    except Exception as exc:
        (staging_dir / "failure.json").write_text(
            json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, indent=2),
            encoding="utf-8",
        )
        package_run(staging_dir, output_zip)
        raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Indeed from an existing Google Chrome instance over CDP."
    )
    parser.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--max-jobs", type=int, default=15)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--no-pause", action="store_true")
    args = parser.parse_args(argv)
    if args.max_jobs < 1 or args.max_jobs > 100:
        parser.error("--max-jobs must be between 1 and 100.")
    if args.max_pages < 1 or args.max_pages > 10:
        parser.error("--max-pages must be between 1 and 10.")
    return args


def main() -> int:
    args = parse_args(sys.argv[1:])
    output = run_capture(
        cdp_endpoint=args.cdp_endpoint,
        api_url=args.api_url,
        output_zip=args.output_zip,
        max_jobs=args.max_jobs,
        max_pages=args.max_pages,
        pause_before_capture=not args.no_pause,
    )
    print(f"Indeed Chrome-attached capture package created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
