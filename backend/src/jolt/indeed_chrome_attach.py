from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
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
    """Allow human verification to finish without treating a slow document as failure."""
    if page.is_closed():
        page = context.new_page()

    def navigate(selected: Page) -> Page:
        # Cloudflare may keep the document loading until the user verifies access.
        # Wait only for navigation to commit; actual job listings are awaited
        # separately, where the operator gets time to complete verification.
        try:
            selected.goto(target_url, wait_until="commit", timeout=60_000)
        except playwright_sync_api.TimeoutError:
            actual = urlparse(selected.url)
            wanted = urlparse(target_url)
            if (
                actual.scheme != wanted.scheme
                or actual.hostname != wanted.hostname
                or actual.path != wanted.path
                or dict(parse_qsl(actual.query)) != dict(parse_qsl(wanted.query))
            ):
                raise
        return selected

    try:
        return navigate(page)
    except playwright_sync_api.Error as exc:
        if "closed" not in str(exc).casefold():
            raise
        return navigate(context.new_page())


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


def _indeed_login_visible(page: Page) -> bool:
    """Identify the Indeed account interstitial without automating login."""
    location = urlparse(page.url or "")
    if (
        location.hostname
        and location.hostname.endswith("indeed.com")
        and location.path.startswith(("/account", "/auth", "/login"))
    ):
        return True
    with contextlib.suppress(playwright_sync_api.Error):
        title = page.title().casefold()
        return (
            "sign in" in title or "iniciar sesión" in title or "iniciar sesion" in title
        ) and "indeed" in title
    return False


def _wait_for_visible_results(
    page: Page,
    max_jobs: int,
    *,
    timeout_ms: int = 600_000,
    evidence_dir: Path | None = None,
    diagnostic_label: str = "indeed_wait",
    readiness_diagnostics: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    elapsed = 0
    announced_verification = False
    started = perf_counter()
    first_dom_seconds: float | None = None
    access_warning_seen = False
    login_seen = False
    poll_count = 0
    while elapsed < timeout_ms:
        poll_count += 1
        # Probe raw DOM before candidate extraction so extractor latency is not
        # incorrectly attributed to Indeed rendering. Diagnostics are optional.
        raw_marker_count = 0
        if readiness_diagnostics is not None:
            with contextlib.suppress(playwright_sync_api.Error):
                raw_marker_count = page.locator("[data-jk]").count()
            if raw_marker_count and first_dom_seconds is None:
                first_dom_seconds = round(perf_counter() - started, 3)
        candidates = _visible_listing_candidates(page, max_jobs)
        if candidates:
            if readiness_diagnostics is not None:
                readiness_diagnostics.update(
                    {
                        "first_dom_listing_seconds": first_dom_seconds,
                        "first_valid_candidate_seconds": round(perf_counter() - started, 3),
                        "raw_listing_marker_count": raw_marker_count,
                        "valid_candidate_count": len(candidates),
                        "poll_count": poll_count,
                        "access_warning_seen": access_warning_seen,
                        "login_seen": login_seen,
                    }
                )
            return candidates

        warning = _access_warning(page)
        login_visible = _indeed_login_visible(page)
        access_warning_seen = access_warning_seen or bool(warning)
        login_seen = login_seen or login_visible
        if (warning or login_visible) and not announced_verification:
            print("Indeed login or verification page detected. Sign in manually if needed.")
            print("JOLT will continue automatically when job results become available.")
            announced_verification = True

        page.wait_for_timeout(500)
        elapsed += 500

    if evidence_dir is not None:
        with contextlib.suppress(Exception):
            page.screenshot(
                path=evidence_dir / f"{diagnostic_label}.png",
                full_page=False,
                timeout=5_000,
            )
        with contextlib.suppress(Exception):
            html = redact_text(page.content())
            (evidence_dir / f"{diagnostic_label}.html").write_text(html, encoding="utf-8")
        with contextlib.suppress(Exception):
            snapshot = page.locator("[data-jk], a[href]").evaluate_all(
                """elements => elements.slice(0, 250).map(element => ({
                    tag: element.tagName,
                    dataJk: element.getAttribute('data-jk') || '',
                    href: element.getAttribute('href') || '',
                    text: (element.innerText || element.getAttribute('aria-label') || '')
                        .replace(/\\s+/g, ' ')
                        .trim()
                        .slice(0, 300)
                }))"""
            )
            (evidence_dir / f"{diagnostic_label}.json").write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )

    if _indeed_login_visible(page):
        raise RuntimeError(
            "Indeed login page remained visible; results were unavailable. "
            "Previous pages are preserved in the partial checkpoint ZIP. "
            "Complete sign-in manually before a new attempt."
        )
    raise RuntimeError(
        "Indeed did not show job results after the supervised verification window. "
        "Previous pages are preserved in the partial checkpoint ZIP."
    )


def _save_partial_checkpoint(
    staging_dir: Path,
    cards: list[CapturedCard],
    pages: list[dict[str, object]],
    *,
    stop_reason: str,
) -> None:
    """Keep recoverable, unsubmitted capture evidence after each completed page.

    Checkpoints are packaged in the output ZIP even if a later page fails.
    Do not POST these items automatically: operator review is required.
    """
    payload = {
        "contract": "jolt-indeed-partial-checkpoint-v1",
        "status": "partial_unsubmitted",
        "stop_reason": stop_reason,
        "captured_count": len(cards),
        "verified_count": sum(card.identity_verified for card in cards),
        "pages": pages,
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
                "page_number": card.page_number,
            }
            for card in cards
        ],
    }
    evidence_dir = staging_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for card in cards:
        if card.detail_html and card.identity_verified:
            evidence_path = evidence_dir / f"job_{card.source_job_id}.redacted.html"
            if not evidence_path.exists():
                evidence_path.write_text(redact_text(card.detail_html), encoding="utf-8")
    checkpoint = staging_dir / "partial_checkpoint.json"
    temporary = staging_dir / "partial_checkpoint.json.tmp"
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    temporary.replace(checkpoint)


def _verified_known_job_ids(source_ids: list[str]) -> set[str]:
    """Read verified local identities; on uncertainty, never skip."""
    if not source_ids or os.getenv("JOLT_DATABASE_URL"):
        return set()
    db = Path(__file__).resolve().parents[2] / "data" / "jolt.db"
    if not db.is_file():
        return set()
    try:
        with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=3) as con:
            placeholders = ",".join("?" for _ in source_ids)
            rows = con.execute(
                "SELECT DISTINCT item.source_job_id FROM capture_items AS item "
                "JOIN capture_runs AS run ON run.id = item.capture_run_id "
                "WHERE run.source = 'indeed' AND item.detail_status = 'verified' "
                "AND item.source_document_id IS NOT NULL "
                f"AND source_job_id IN ({placeholders})",
                source_ids,
            ).fetchall()
        return {str(row[0]) for row in rows}
    except (sqlite3.Error, OSError):
        return set()


def run_capture(
    *,
    cdp_endpoint: str,
    api_url: str,
    output_zip: Path,
    max_jobs: int,
    max_pages: int,
    pause_before_capture: bool,
    search_url: str | None = None,
) -> Path:
    capture_started = perf_counter()
    staging_dir = Path(tempfile.mkdtemp(prefix="jolt_indeed_cdp_"))
    evidence_dir = staging_dir / "evidence"
    evidence_dir.mkdir(parents=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(cdp_endpoint, timeout=30_000)
            context, attached_page = _select_indeed_page(browser)

            if search_url:
                requested = urlparse(search_url)
                if (
                    requested.scheme != "https"
                    or requested.hostname not in {"es.indeed.com", "www.indeed.com", "indeed.com"}
                    or requested.path != "/jobs"
                ):
                    raise ValueError("Expected HTTPS Indeed /jobs search URL")
                attached_page = _navigate_search_page(context, attached_page, search_url)
                # Do not attach to an old tab or a stale visible result set.
                actual = urlparse(attached_page.url)
                expected_query = dict(parse_qsl(requested.query, keep_blank_values=True))
                actual_query = dict(parse_qsl(actual.query, keep_blank_values=True))
                for key in ("q", "l", "fromage", "sort", "radius"):
                    if key in expected_query and actual_query.get(key) != expected_query[key]:
                        raise RuntimeError(
                            f"Indeed search navigation mismatch: {key} differs from requested URL"
                        )

            with contextlib.suppress(Exception):
                attached_page.screenshot(
                    path=evidence_dir / "01_attached_search.png",
                    full_page=False,
                )

            print("JOLT is attached to Google Chrome.")
            print("Waiting for visible Indeed job results...")
            _wait_for_visible_results(
                attached_page,
                1,
                evidence_dir=evidence_dir,
                diagnostic_label="initial_wait_timeout",
            )

            base_search_url = _page_search_url(attached_page.url, 1)
            page = attached_page
            cards: list[CapturedCard] = []
            job_timings: list[dict[str, object]] = []
            pages: list[dict[str, object]] = []
            seen_job_ids: set[str] = set()
            result_position = 0
            exhausted = False
            verified_known_skip_count = 0
            unique_known_ids: set[str] = set()
            previous_ids: set[str] | None = None
            identical_streak = 0

            for page_number in range(1, max_pages + 1):
                if len(cards) >= max_jobs:
                    break

                page_started = perf_counter()
                navigation_started = perf_counter()
                target_url = _page_search_url(base_search_url, page_number)
                if page_number > 1:
                    print(f"Opening Indeed results page {page_number}: {target_url}")
                    page = _navigate_search_page(context, page, target_url)
                navigation_seconds = perf_counter() - navigation_started
                results_wait_started = perf_counter()

                readiness_diagnostics: dict[str, object] = {}
                candidates = _wait_for_visible_results(
                    page,
                    15,
                    evidence_dir=evidence_dir,
                    diagnostic_label=f"page_{page_number:02d}_wait_timeout",
                    readiness_diagnostics=readiness_diagnostics,
                )
                results_wait_seconds = perf_counter() - results_wait_started
                visible_ids = [candidate["source_job_id"] for candidate in candidates]
                # Preserve exactly what the page exposes; no claim that
                # sponsored listings or displayed age are always detectable.
                listing_signals = page.evaluate(
                    """() => {
                        const results = {};
                        for (const node of document.querySelectorAll('[data-jk]')) {
                            const id = node.getAttribute('data-jk');
                            if (!id || results[id]) continue;
                            const card = node.closest('.slider_item, .job_seen_beacon, .jobsearch-SerpJobCard, li') || node;
                            const text = (card.innerText || '').replace(/\\s+/g, ' ').trim();
                            const sponsoredLabel = text.match(/\\b(sponsored|patrocinad[oa]s?|promocionad[oa]s?)\\b/i);
                            const age = text.match(/(?:hace\\s+)?(?:\\d+\\s*(?:d[ií]as?|hours?|horas?|minutes?|minutos?)|hoy|justo ahora|today|just posted)/i);
                            results[id] = {
                                sponsored_label_detected: Boolean(sponsoredLabel),
                                sponsored_label: sponsoredLabel ? sponsoredLabel[0] : null,
                                displayed_age: age ? age[0] : null,
                                detection_scope: 'listing_container_text_heuristic',
                            };
                        }
                        return results;
                    }"""
                )
                pages.append(
                    {
                        "page_number": page_number,
                        "navigation_seconds": round(navigation_seconds, 3),
                        "results_wait_seconds": round(results_wait_seconds, 3),
                        "readiness_diagnostics": readiness_diagnostics,
                        "visible_job_ids": visible_ids,
                        "listing_signals": {
                            job_id: listing_signals.get(job_id, {}) for job_id in visible_ids
                        },
                        "observed_search_url": page.url,
                    }
                )

                verified_known = _verified_known_job_ids(visible_ids)
                verified_known_skip_count += len(verified_known)
                unique_known_ids.update(verified_known)
                pages[-1]["skipped_verified_known_ids"] = sorted(verified_known)
                new_candidates = [
                    candidate
                    for candidate in candidates
                    if candidate["source_job_id"] not in seen_job_ids
                    and candidate["source_job_id"] not in verified_known
                ]
                if pause_before_capture:
                    print(
                        f"Page {page_number}: {len(candidates)} visible, "
                        f"{len(new_candidates)} unseen after deduplication; "
                        f"{len(verified_known)} verified known."
                    )

                current_ids = set(visible_ids)
                repeated = bool(current_ids) and current_ids == previous_ids
                identical_streak = identical_streak + 1 if repeated else 0
                previous_ids = current_ids
                pages[-1]["identical_to_previous_page"] = repeated
                pages[-1]["unseen_candidate_count"] = len(new_candidates)
                if identical_streak >= 2 and not new_candidates:
                    exhausted = True
                    print("Stopping after three identical pages without unseen offers.")
                    break
                if not new_candidates:
                    print(f"Page {page_number}: no unseen jobs, continuing pagination.")
                    continue

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

                    job_started = perf_counter()
                    print(
                        f"Capturing job {len(cards) + 1}/{max_jobs}: "
                        f"{title_hint[:65]} [{source_job_id}]",
                        flush=True,
                    )
                    clicked = _click_listing_candidate(page, source_job_id)
                    if not clicked and page.is_closed():
                        page = _navigate_search_page(context, page, target_url)
                        clicked = _click_listing_candidate(page, source_job_id)

                    click_seconds = round(perf_counter() - job_started, 3)
                    if not clicked:
                        job_timings.append(
                            {
                                "source_job_id": source_job_id,
                                "click_seconds": click_seconds,
                                "verified": False,
                                "error": "click_failed",
                            }
                        )
                        print(f"  Selection failed after {click_seconds:.2f}s", flush=True)
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

                    print("  Card selected; checking detail identity...", flush=True)
                    panel_ready = _wait_for_detail_panel(page, source_job_id, title_hint)
                    panel_seconds = round(perf_counter() - job_started - click_seconds, 3)
                    detail_timings: list[dict[str, object]] = []
                    title, company, location, description, verified, reason = _detail_fields(
                        page, source_job_id, title_hint, timings=detail_timings
                    )
                    for timing in detail_timings:
                        print(
                            f"    Detail timing: {timing['step']}={timing['seconds']}s",
                            flush=True,
                        )
                    extraction_seconds = round(
                        perf_counter() - job_started - click_seconds - panel_seconds, 3
                    )
                    if not panel_ready and verified:
                        verified = False
                        reason = (
                            "Indeed detail panel did not become stable after the listing click."
                        )

                    print(
                        f"  Detail extracted: verified={verified}; "
                        f"company={company[:50]!r}; location={location[:50]!r}",
                        flush=True,
                    )
                    detail_html = page.content() if verified else ""
                    # Verified listings already retain redacted HTML evidence.
                    # A per-job screenshot can cost its full five-second timeout;
                    # reserve screenshots for unsuccessful captures/diagnostics.
                    if not verified:
                        with contextlib.suppress(Exception):
                            page.screenshot(
                                path=evidence_dir / f"p{page_number:02d}_job_{source_job_id}.png",
                                full_page=False,
                                timeout=5_000,
                            )

                    evidence_seconds = round(
                        perf_counter()
                        - job_started
                        - click_seconds
                        - panel_seconds
                        - extraction_seconds,
                        3,
                    )
                    total_seconds = round(perf_counter() - job_started, 3)
                    job_timings.append(
                        {
                            "source_job_id": source_job_id,
                            "click_seconds": click_seconds,
                            "panel_seconds": panel_seconds,
                            "extraction_seconds": extraction_seconds,
                            "evidence_seconds": evidence_seconds,
                            "total_seconds": total_seconds,
                            "description_characters": len(description),
                            "detail_timings": detail_timings,
                            "verified": verified,
                        }
                    )
                    print(
                        f"  Timing: click={click_seconds:.2f}s "
                        f"panel={panel_seconds:.2f}s extraction={extraction_seconds:.2f}s "
                        f"evidence={evidence_seconds:.2f}s total={total_seconds:.2f}s "
                        f"description_chars={len(description)}",
                        flush=True,
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

                checkpoint_started = perf_counter()
                _save_partial_checkpoint(staging_dir, cards, pages, stop_reason="page_completed")
                checkpoint_seconds = perf_counter() - checkpoint_started
                page_total_seconds = perf_counter() - page_started
                pages[-1]["checkpoint_seconds"] = round(checkpoint_seconds, 3)
                pages[-1]["page_total_seconds"] = round(page_total_seconds, 3)
                print(
                    f"Page {page_number} timing: navigate={navigation_seconds:.2f}s "
                    f"results_wait={results_wait_seconds:.2f}s "
                    f"first_dom={readiness_diagnostics.get('first_dom_listing_seconds')}s "
                    f"valid_candidate={readiness_diagnostics.get('first_valid_candidate_seconds')}s "
                    f"login_seen={readiness_diagnostics.get('login_seen')} "
                    f"checkpoint={checkpoint_seconds:.2f}s "
                    f"total={page_total_seconds:.2f}s",
                    flush=True,
                )
                print(
                    f"Progress: page {page_number}/{max_pages} · captured {len(cards)}/{max_jobs}"
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
                "verified_known_skips": verified_known_skip_count,
                "unique_verified_known_ids": len(unique_known_ids),
                "elapsed_seconds": round(perf_counter() - capture_started, 3),
                "captured_count": len(cards),
                "verified_count": sum(card.identity_verified for card in cards),
                "stop_reason": stop_reason,
                "pages": pages,
                "job_timings": job_timings,
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

            # Reuse HTML evidence persisted by checkpoints at each page.
            for card in cards:
                if card.detail_html:
                    evidence_path = evidence_dir / f"job_{card.source_job_id}.redacted.html"
                    if not evidence_path.exists():
                        evidence_path.write_text(redact_text(card.detail_html), encoding="utf-8")

            # Empty sets are not accepted by the live capture API (min_items=1).
            # Preserve evidence and distinguish known-only from extraction gaps.
            if not cards:
                visible = {
                    job_id for page_info in pages
                    for job_id in page_info.get("visible_job_ids", [])
                }
                all_known = bool(visible) and unique_known_ids.issuperset(visible)
                api_result = {
                    "submitted": False,
                    "status": "no_new_jobs" if all_known else "no_captured_jobs",
                    "reason": (
                        "all_visible_offers_previously_verified"
                        if all_known else "no_new_extractable_offers"
                    ),
                    "unique_visible_count": len(visible),
                    "unique_known_count": len(unique_known_ids),
                    "capture_run_id": None,
                }
            else:
                api_result = submit_capture(api_url, cards, base_search_url, max_jobs, pages)
            if api_result.get("capture_run_id") and api_result.get("status") in {
                "completed",
                "completed_with_warnings",
            }:
                (staging_dir / "partial_checkpoint.json").unlink(missing_ok=True)
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
                            "API result: "
                            + str(
                                api_result.get("status")
                                or api_result.get("error")
                                or (
                                    "persisted"
                                    if api_result.get("capture_run_id")
                                    else "not_persisted"
                                )
                            ),
                        ]
                    )
                ),
                encoding="utf-8",
            )

        return package_run(staging_dir, output_zip)
    except Exception as exc:
        if "cards" in locals() and "pages" in locals():
            _save_partial_checkpoint(
                staging_dir, cards, pages, stop_reason="interrupted_before_submission"
            )
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
    parser.add_argument("--search-url", default="")
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--max-jobs", type=int, default=15)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--no-pause", action="store_true")
    args = parser.parse_args(argv)
    if args.max_jobs < 1 or args.max_jobs > 200:
        parser.error("--max-jobs must be between 1 and 200.")
    if args.max_pages < 1 or args.max_pages > 20:
        parser.error("--max-pages must be between 1 and 20.")
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
        search_url=args.search_url or None,
    )
    print(f"Indeed Chrome-attached capture package created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
