from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Locator, Page, TimeoutError, sync_playwright

DEFAULT_SEARCH_URL = "https://www.linkedin.com/jobs/search/"
DEFAULT_API_URL = "http://127.0.0.1:8000"
CARD_SELECTOR = ".jobs-search-results__list-item"
TITLE_LINK_SELECTOR = "a.job-card-list__title"
DETAIL_SELECTOR = ".jobs-search__job-details--container"


@dataclass(frozen=True)
class CapturedCard:
    source_job_id: str
    source_url: str
    title: str
    company: str
    location: str
    detail_html: str
    identity_verified: bool
    verification_reason: str


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def redact_text(value: str) -> str:
    value = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[^\s\"']+", r"\1[REDACTED]", value)
    value = re.sub(
        r"(?i)(csrf|token|session|cookie)([\"'=:\s]+)[^\s\"'<>]+", r"\1\2[REDACTED]", value
    )
    value = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[REDACTED_EMAIL]", value, flags=re.I)
    value = re.sub(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)", "[REDACTED_PHONE]", value)
    return value


def extract_job_id(value: str) -> str:
    match = re.search(r"(?:currentJobId=|/jobs/view/|/view/)(\d+)", value)
    return match.group(1) if match else ""


def safe_text(locator: Locator) -> str:
    try:
        return " ".join(locator.first.inner_text(timeout=2_000).split())
    except TimeoutError:
        return ""


def detail_matches(page: Page, expected_job_id: str) -> bool:
    panel = page.locator(DETAIL_SELECTOR).first
    if panel.count() == 0:
        return False
    panel_id = panel.get_attribute("data-job-id") or ""
    if panel_id == expected_job_id:
        return True
    links = panel.locator("a[href*='/jobs/view/']")
    if links.count() == 0:
        return False
    href = links.first.get_attribute("href") or ""
    return extract_job_id(href) == expected_job_id


def wait_for_expected_detail(page: Page, expected_job_id: str, timeout_ms: int = 12_000) -> bool:
    try:
        page.wait_for_function(
            """
            ([selector, expected]) => {
              const panel = document.querySelector(selector);
              if (!panel) return false;
              if (panel.getAttribute('data-job-id') === expected) return true;
              const link = panel.querySelector("a[href*='/jobs/view/']");
              return Boolean(link && link.href.includes(expected));
            }
            """,
            arg=[DETAIL_SELECTOR, expected_job_id],
            timeout=timeout_ms,
        )
    except TimeoutError:
        return False
    return detail_matches(page, expected_job_id)


def _card_identity(card: Locator) -> tuple[str, str]:
    source_job_id = card.get_attribute("data-job-id") or ""
    title_link = card.locator(TITLE_LINK_SELECTOR).first
    source_url = title_link.get_attribute("href") or ""
    return source_job_id or extract_job_id(source_url), source_url


def capture_visible_cards(page: Page, max_jobs: int, evidence_dir: Path) -> list[CapturedCard]:
    cards = page.locator(CARD_SELECTOR)
    count = min(cards.count(), max_jobs)
    captured: list[CapturedCard] = []
    seen: set[str] = set()

    for index in range(count):
        card = cards.nth(index)
        source_job_id, source_url = _card_identity(card)
        if not source_job_id or source_job_id in seen:
            continue
        seen.add(source_job_id)
        title = safe_text(card.locator(TITLE_LINK_SELECTOR))
        company = safe_text(card.locator(".job-card-container__primary-description"))
        location = safe_text(card.locator(".job-card-container__metadata-item"))

        try:
            card.locator(TITLE_LINK_SELECTOR).first.click(timeout=8_000)
        except TimeoutError:
            captured.append(
                CapturedCard(
                    source_job_id=source_job_id,
                    source_url=source_url,
                    title=title,
                    company=company,
                    location=location,
                    detail_html="",
                    identity_verified=False,
                    verification_reason="Listing click timed out.",
                )
            )
            continue

        verified = wait_for_expected_detail(page, source_job_id)
        detail_html = page.content() if verified else ""
        reason = (
            "" if verified else "Detail panel did not reach the expected LinkedIn job identity."
        )
        page.screenshot(path=evidence_dir / f"job_{source_job_id}.png", full_page=False)
        captured.append(
            CapturedCard(
                source_job_id=source_job_id,
                source_url=source_url,
                title=title,
                company=company,
                location=location,
                detail_html=detail_html,
                identity_verified=verified,
                verification_reason=reason,
            )
        )
    return captured


def submit_capture(
    api_url: str, listing_html: str, cards: list[CapturedCard], search_url: str
) -> dict[str, Any]:
    detail_map = {
        card.source_job_id: card.detail_html
        for card in cards
        if card.identity_verified and card.detail_html
    }
    payload = json.dumps(
        {
            "listing_html": listing_html,
            "detail_html_by_job_id": detail_map,
            "search_url": search_url,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/captures/linkedin/fixture",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"submitted": False, "error": str(exc)}


def package_run(staging_dir: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging_dir))
    return destination


def run_capture(
    search_url: str,
    api_url: str,
    profile_dir: Path,
    output_zip: Path,
    max_jobs: int,
    pause_for_login: bool,
) -> Path:
    staging_dir = Path(tempfile.mkdtemp(prefix="jolt_linkedin_"))
    evidence_dir = staging_dir / "evidence"
    evidence_dir.mkdir(parents=True)
    log: list[str] = []

    try:
        with sync_playwright() as playwright:
            context: BrowserContext = playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1440, "height": 1000},
                args=["--disable-blink-features=AutomationControlled"],
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

            page.wait_for_selector(CARD_SELECTOR, timeout=60_000)
            listing_html = page.content()
            cards = capture_visible_cards(page, max_jobs=max_jobs, evidence_dir=evidence_dir)
            page.screenshot(path=evidence_dir / "99_capture_complete.png", full_page=False)
            context.tracing.stop(path=evidence_dir / "playwright_trace.zip")
            context.close()

        summary = {
            "search_url": search_url,
            "captured_at": datetime.now(UTC).isoformat(),
            "max_jobs": max_jobs,
            "captured_count": len(cards),
            "verified_count": sum(card.identity_verified for card in cards),
            "cards": [asdict(card) | {"detail_html": "[stored separately]"} for card in cards],
        }
        (staging_dir / "capture_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
        )
        (staging_dir / "listing_page.redacted.html").write_text(
            redact_text(listing_html), encoding="utf-8"
        )
        for card in cards:
            if card.detail_html:
                (evidence_dir / f"job_{card.source_job_id}.redacted.html").write_text(
                    redact_text(card.detail_html), encoding="utf-8"
                )

        api_result = submit_capture(api_url, listing_html, cards, search_url)
        (staging_dir / "api_result.json").write_text(
            json.dumps(api_result, indent=2, ensure_ascii=True), encoding="utf-8"
        )
        log.append(f"Captured {len(cards)} visible jobs.")
        log.append(f"Verified {sum(card.identity_verified for card in cards)} detail panels.")
        log.append(f"API result: {api_result.get('status', api_result.get('error', 'unknown'))}")
        (staging_dir / "run.log").write_text(redact_text("\n".join(log)), encoding="utf-8")
        return package_run(staging_dir, output_zip)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a bounded supervised LinkedIn capture.")
    parser.add_argument("--search-url", default=DEFAULT_SEARCH_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--max-jobs", type=int, default=10)
    parser.add_argument("--no-login-pause", action="store_true")
    args = parser.parse_args(argv)
    if args.max_jobs < 1 or args.max_jobs > 50:
        parser.error("--max-jobs must be between 1 and 50.")
    return args


def main() -> int:
    args = parse_args(sys.argv[1:])
    output = run_capture(
        search_url=args.search_url,
        api_url=args.api_url,
        profile_dir=args.profile_dir,
        output_zip=args.output_zip,
        max_jobs=args.max_jobs,
        pause_for_login=not args.no_login_pause,
    )
    print(f"Capture package created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
