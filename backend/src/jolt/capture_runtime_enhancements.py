from __future__ import annotations

import contextlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page, TimeoutError

from jolt import multipage_capture
from jolt.supervised_capture import CapturedCard, safe_text, wait_for_expected_detail

_original_capture_pages = multipage_capture.capture_pages
_last_pages: list[multipage_capture.PageEvidence] = []


def _click_with_one_retry(title_link: Locator, card: Locator) -> bool:
    active_link = title_link
    for attempt in range(2):
        try:
            active_link.click(timeout=8_000)
            return True
        except TimeoutError:
            if attempt == 0:
                with contextlib.suppress(TimeoutError):
                    card.scroll_into_view_if_needed(timeout=2_000)
                refreshed = multipage_capture._title_link(card)
                if refreshed is not None:
                    active_link = refreshed
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
                    page_number, index, "", "Card had no usable LinkedIn job identity."
                )
            )
            continue
        if source_job_id in seen:
            skipped.append(
                multipage_capture.SkippedCard(
                    page_number, index, source_job_id, "Duplicate job identity across pages."
                )
            )
            continue
        if title_link is None:
            skipped.append(
                multipage_capture.SkippedCard(
                    page_number, index, source_job_id, "Card had no supported title link."
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
                    source_job_id=source_job_id,
                    source_url=source_url,
                    title=title,
                    company=company,
                    location=location,
                    detail_html="",
                    description="",
                    identity_verified=False,
                    verification_reason="Listing click timed out after one retry.",
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


def capture_pages(*args: Any, **kwargs: Any):
    global _last_pages
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


def main() -> int:
    multipage_capture.capture_page_cards = capture_page_cards
    multipage_capture.capture_pages = capture_pages
    multipage_capture.submit_capture = submit_capture
    return multipage_capture.main()
