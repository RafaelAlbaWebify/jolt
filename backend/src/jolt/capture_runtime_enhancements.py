from __future__ import annotations

import contextlib
import json
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Locator, Page, TimeoutError

from jolt import multipage_capture
from jolt.supervised_capture import CapturedCard, safe_text, wait_for_expected_detail

_original_capture_pages = multipage_capture.capture_pages
_last_pages: list[multipage_capture.PageEvidence] = []
_search_state: dict[str, Any] = {}
_retry_metrics: dict[str, int] = {}

_IGNORED_FILTER_LABELS = {
    "following",
    "follow",
    "jobs",
    "my jobs",
    "notifications",
}


def _reset_runtime_state() -> None:
    global _last_pages, _search_state, _retry_metrics
    _last_pages = []
    _search_state = {}
    _retry_metrics = {
        "retry_attempted_count": 0,
        "recovered_after_retry_count": 0,
        "failed_after_retry_count": 0,
    }


def _click_with_one_retry(title_link: Locator, card: Locator) -> bool:
    active_link = title_link
    for attempt in range(2):
        try:
            active_link.click(timeout=8_000)
            if attempt == 1:
                _retry_metrics["recovered_after_retry_count"] += 1
            return True
        except TimeoutError:
            if attempt == 0:
                _retry_metrics["retry_attempted_count"] += 1
                with contextlib.suppress(TimeoutError):
                    card.scroll_into_view_if_needed(timeout=2_000)
                refreshed = multipage_capture._title_link(card)
                if refreshed is not None:
                    active_link = refreshed
    _retry_metrics["failed_after_retry_count"] += 1
    return False


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
    if not normalized:
        return False
    return normalized.casefold() not in _IGNORED_FILTER_LABELS


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
    parsed = urlparse(page.url)
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
        "effective_url": page.url,
        "keywords": keywords,
        "location": location,
        "active_filter_labels": _active_filter_labels(page),
        "url_filter_parameters": {
            key: values
            for key, values in query.items()
            if key.startswith("f_") or key in {"geoId", "distance", "sortBy"}
        },
    }


def capture_page_cards(
    page: Page,
    cards: Locator,
    *,
    page_number: int,
    remaining: int,
    evidence_dir: Path,
    seen: set[str],
    skipped: list[multipage_capture.SkippedCard],
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
            card, multipage_capture.COMPANY_SELECTORS
        )
        location_locator = multipage_capture._first_existing(
            card, multipage_capture.LOCATION_SELECTORS
        )
        company = safe_text(company_locator) if company_locator is not None else ""
        location = safe_text(location_locator) if location_locator is not None else ""

        if not _click_with_one_retry(title_link, card):
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


def capture_pages(*args: Any, **kwargs: Any):
    global _last_pages, _search_state
    page = args[0] if args else kwargs.get("page")
    if isinstance(page, Page):
        _search_state = extract_search_state(page)
    result = _original_capture_pages(*args, **kwargs)
    _last_pages = list(result[1])
    return result


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
            "pages": [
                {
                    "page_number": page.page_number,
                    "visible_job_ids": list(page.visible_job_ids),
                    "next_control_present": page.next_control_present,
                    "next_control_enabled": page.next_control_enabled,
                }
                for page in _last_pages
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


def _argument_value(name: str) -> str:
    try:
        index = sys.argv.index(name)
    except ValueError:
        return ""
    return sys.argv[index + 1] if index + 1 < len(sys.argv) else ""


def _amend_capture_package(output_zip: Path) -> None:
    if not output_zip.exists():
        return
    with tempfile.TemporaryDirectory(prefix="jolt_observability_") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(output_zip) as archive:
            archive.extractall(root)

        summary_path = root / "capture_summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["search_state"] = _search_state
            summary["retry_metrics"] = dict(_retry_metrics)
            summary_path.write_text(
                json.dumps(summary, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )

        run_log = root / "run.log"
        if run_log.exists():
            with run_log.open("a", encoding="utf-8") as stream:
                stream.write(
                    f"\nRetry attempts: {_retry_metrics['retry_attempted_count']}"
                    f"\nRecovered after retry: "
                    f"{_retry_metrics['recovered_after_retry_count']}"
                    f"\nFailed after retry: {_retry_metrics['failed_after_retry_count']}\n"
                )

        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root))


def main() -> int:
    _reset_runtime_state()
    multipage_capture.capture_page_cards = capture_page_cards
    multipage_capture.capture_pages = capture_pages
    multipage_capture.submit_capture = submit_capture
    result = multipage_capture.main()
    output = _argument_value("--output-zip")
    if output:
        _amend_capture_package(Path(output))
    return result
