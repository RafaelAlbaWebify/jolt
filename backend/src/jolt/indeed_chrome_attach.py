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


def run_capture(
    *,
    cdp_endpoint: str,
    api_url: str,
    output_zip: Path,
    max_jobs: int,
    pause_before_capture: bool,
) -> Path:
    staging_dir = Path(tempfile.mkdtemp(prefix="jolt_indeed_cdp_"))
    evidence_dir = staging_dir / "evidence"
    evidence_dir.mkdir(parents=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(cdp_endpoint, timeout=30_000)
            _, page = _select_indeed_page(browser)

            warning = _access_warning(page)
            if warning:
                raise RuntimeError(warning)

            with contextlib.suppress(Exception):
                page.screenshot(path=evidence_dir / "01_attached_search.png", full_page=False)

            if pause_before_capture:
                print("JOLT is attached to the existing Google Chrome instance.")
                print("Keep the Indeed search results visible in that Chrome window.")
                print("Resolve any verification manually before continuing.")
                input("Press Enter to capture up to the requested number of visible jobs: ")

            warning = _access_warning(page)
            if warning:
                raise RuntimeError(warning)

            search_url = page.url
            candidates = _visible_listing_candidates(page, max_jobs)
            if not candidates:
                raise RuntimeError(
                    "No visible Indeed job links with durable job keys were found "
                    "in the attached Chrome tab."
                )

            cards: list[CapturedCard] = []
            for position, candidate in enumerate(candidates, 1):
                source_job_id = candidate["source_job_id"]
                source_url = candidate["source_url"]
                title_hint = candidate["title"]

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
                            result_position=position,
                            page_number=1,
                            card_index=position - 1,
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
                    reason = "Indeed detail panel did not become stable after the listing click."

                detail_html = page.content() if verified else ""
                with contextlib.suppress(Exception):
                    page.screenshot(
                        path=evidence_dir / f"job_{source_job_id}.png",
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
                        result_position=position,
                        page_number=1,
                        card_index=position - 1,
                    )
                )

            summary = {
                "source": "indeed",
                "mode": "chrome_cdp_attach",
                "cdp_endpoint": cdp_endpoint,
                "search_url": search_url,
                "captured_at": datetime.now(UTC).isoformat(),
                "max_jobs": max_jobs,
                "captured_count": len(cards),
                "verified_count": sum(card.identity_verified for card in cards),
                "stop_reason": (
                    "requested_limit_reached"
                    if len(cards) >= max_jobs
                    else "visible_jobs_exhausted"
                ),
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

            api_result = submit_capture(api_url, cards, search_url, max_jobs)
            (staging_dir / "api_result.json").write_text(
                json.dumps(api_result, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
            (staging_dir / "run.log").write_text(
                redact_text(
                    "\n".join(
                        [
                            "Mode: attached Google Chrome over CDP.",
                            f"Captured {len(cards)} visible Indeed jobs.",
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
    parser.add_argument("--max-jobs", type=int, default=5)
    parser.add_argument("--no-pause", action="store_true")
    args = parser.parse_args(argv)
    if args.max_jobs < 1 or args.max_jobs > 10:
        parser.error("--max-jobs must be between 1 and 10.")
    return args


def main() -> int:
    args = parse_args(sys.argv[1:])
    output = run_capture(
        cdp_endpoint=args.cdp_endpoint,
        api_url=args.api_url,
        output_zip=args.output_zip,
        max_jobs=args.max_jobs,
        pause_before_capture=not args.no_pause,
    )
    print(f"Indeed Chrome-attached capture package created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
