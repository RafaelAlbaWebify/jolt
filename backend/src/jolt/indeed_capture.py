from __future__ import annotations

import argparse
import contextlib
import html
import json
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import Page, sync_playwright
from pydantic import ValidationError

from jolt.schemas import IndeedLiveCaptureItemRequest, IndeedLiveCaptureRequest
from jolt.supervised_capture import CapturedCard, package_run, redact_text

DEFAULT_SEARCH_URL = "https://es.indeed.com/jobs"
DEFAULT_API_URL = "http://127.0.0.1:8000"


def extract_indeed_job_key(value: str) -> str:
    if not value.strip():
        return ""
    parsed = urlparse(value.strip())
    if not parsed.hostname or "indeed." not in parsed.hostname.casefold():
        return ""
    query = parse_qs(parsed.query)
    for key in ("jk", "vjk"):
        values = query.get(key)
        if values and values[0].strip():
            return values[0].strip()
    return ""


def canonical_indeed_job_url(value: str) -> str:
    key = extract_indeed_job_key(value)
    return f"https://es.indeed.com/viewjob?jk={key}" if key else value.strip()


def _text(locator) -> str:
    try:
        return " ".join(locator.inner_text(timeout=2_000).split())
    except Exception:
        return ""


def _raw_text(locator) -> str:
    try:
        return locator.inner_text(timeout=2_000).strip()
    except Exception:
        return ""


def _is_action_link_text(value: str) -> bool:
    normalized = " ".join(value.split()).casefold()
    action_markers = (
        "ver empleos similares",
        "view similar jobs",
        "solicitar en la página de la empresa",
        "solicitar en la pagina de la empresa",
        "apply on company site",
        "apply on company website",
        "guardar empleo",
        "save job",
    )
    return any(marker in normalized for marker in action_markers)


def _listing_candidate_nodes(page: Page):
    return page.locator(
        "h2.jobTitle a, "
        "a.jcs-JobTitle, "
        "a[data-testid='job-title'], "
        "a[href*='viewjob'], "
        "a[href*='jk='], "
        "[data-jk]"
    )


def _node_job_key(page: Page, node) -> str:
    href = (node.get_attribute("href") or "").strip()
    if href:
        key = extract_indeed_job_key(urljoin(page.url, href))
        if key:
            return key
    return (node.get_attribute("data-jk") or "").strip()


def _node_title(node) -> str:
    tag_name = ""
    with contextlib.suppress(Exception):
        tag_name = str(node.evaluate("element => element.tagName") or "").casefold()

    if tag_name == "a":
        title = _text(node) or (node.get_attribute("aria-label") or "").strip()
        if title and not _is_action_link_text(title):
            return title

    for selector in (
        "h2.jobTitle a",
        "a.jcs-JobTitle",
        "a[data-testid='job-title']",
        "h2.jobTitle",
    ):
        nested = node.locator(selector).first
        value = _text(nested) or (nested.get_attribute("aria-label") or "").strip()
        if value and not _is_action_link_text(value):
            return value

    title = _text(node) or (node.get_attribute("aria-label") or "").strip()
    if title and not _is_action_link_text(title):
        return title
    return ""


def _visible_listing_candidates(page: Page, max_jobs: int) -> list[dict[str, str]]:
    nodes = _listing_candidate_nodes(page)
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    try:
        count = min(nodes.count(), 200)
    except Exception:
        return []

    for index in range(count):
        node = nodes.nth(index)
        try:
            if not node.is_visible():
                continue
        except Exception:
            continue

        source_job_id = _node_job_key(page, node)
        if not source_job_id or source_job_id in seen:
            continue

        title = _node_title(node)
        if not title:
            continue

        seen.add(source_job_id)
        candidates.append(
            {
                "source_job_id": source_job_id,
                "source_url": canonical_indeed_job_url(
                    f"https://es.indeed.com/viewjob?jk={source_job_id}"
                ),
                "title": title[:240],
            }
        )
        if len(candidates) >= max_jobs:
            break
    return candidates


def _click_listing_candidate(page: Page, source_job_id: str) -> bool:
    # Directly target the exact Indeed job key instead of repeatedly enumerating
    # every listing node and issuing CDP calls for unrelated cards.
    key = json.dumps(source_job_id)
    selectors = (
        f"a[data-jk={key}]",
        f"[data-jk={key}] a.jcs-JobTitle",
        f"[data-jk={key}] h2.jobTitle a",
        f"a[href*={json.dumps('jk=' + source_job_id)}]",
        f"[data-jk={key}]",
    )
    for selector in selectors:
        node = page.locator(selector).first
        try:
            if not node.is_visible(timeout=300):
                continue
            node.scroll_into_view_if_needed(timeout=2_000)
            node.click(timeout=4_000)
            return True
        except Exception:
            continue
    return False


def _wait_for_detail_panel(
    page: Page,
    expected_id: str,
    expected_title: str,
    *,
    timeout_ms: int = 10_000,
) -> bool:
    elapsed = 0
    while elapsed < timeout_ms:
        current_id = extract_indeed_job_key(page.url)
        panel = _panel_container(page, expected_title)
        if panel is not None and current_id == expected_id:
            return True

        page.wait_for_timeout(250)
        elapsed += 250
    return False


def _strip_html(value: str) -> str:
    value = re.sub(r"<\s*br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</\s*(?:p|li|div|h\d)\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return "\n".join(line.strip() for line in html.unescape(value).splitlines() if line.strip())


def _jobposting_jsonld(page: Page) -> dict[str, object]:
    scripts = page.locator("script[type='application/ld+json']")
    try:
        count = min(scripts.count(), 20)
    except Exception:
        return {}
    for index in range(count):
        try:
            raw = scripts.nth(index).text_content(timeout=1_000) or ""
            parsed = json.loads(raw)
        except Exception:
            continue
        queue = parsed if isinstance(parsed, list) else [parsed]
        while queue:
            item = queue.pop(0)
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "JobPosting":
                return item
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
    return {}


def _location_from_jsonld(data: dict[str, object]) -> str:
    raw = data.get("jobLocation")
    locations = raw if isinstance(raw, list) else [raw]
    parts: list[str] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get("address")
        if not isinstance(address, dict):
            continue
        chunk = ", ".join(
            str(address.get(key, "")).strip()
            for key in (
                "streetAddress",
                "addressLocality",
                "addressRegion",
                "postalCode",
                "addressCountry",
            )
            if str(address.get(key, "")).strip()
        )
        if chunk and chunk not in parts:
            parts.append(chunk)
    return " | ".join(parts)


def _first_text(page: Page, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        value = _text(page.locator(selector).first)
        if value:
            return value
    return ""


def _panel_container(page: Page, expected_title: str):
    # Indeed usually exposes a stable detail-pane container. Check it first:
    # traversing thirty ancestors and reading each inner_text can cost seconds
    # per listing even when the target pane was already rendered.
    selectors = (
        "#jobsearch-ViewjobPaneWrapper",
        "[data-testid='jobsearch-ViewJobLayout-jobDisplay']",
        "[data-testid='jobsearch-JobComponent']",
        "#vjs-container",
    )
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.is_visible(timeout=300):
                text = _text(locator)
                if expected_title.casefold() in text.casefold():
                    return locator
        except Exception:
            continue

    # Fallback for variants where Indeed does not expose known pane selectors.
    title_locator = page.get_by_text(expected_title, exact=True)
    try:
        title_count = min(title_locator.count(), 10)
    except Exception:
        title_count = 0

    best = None
    best_len = 10**9
    for title_index in range(title_count):
        title_node = title_locator.nth(title_index)
        try:
            if not title_node.is_visible():
                continue
        except Exception:
            continue
        ancestors = title_node.locator("xpath=ancestor::div")
        try:
            ancestor_count = min(ancestors.count(), 30)
        except Exception:
            ancestor_count = 0
        for ancestor_index in range(ancestor_count):
            ancestor = ancestors.nth(ancestor_index)
            text = _text(ancestor)
            normalized = text.casefold()
            if expected_title.casefold() not in normalized:
                continue
            if "detalles del empleo" not in normalized and "job details" not in normalized:
                continue
            if "empleos de " in normalized and len(text) > 2500:
                continue
            if len(text) < best_len:
                best = ancestor
                best_len = len(text)
    return best


def _scroll_panel_to_description(panel, *, max_steps: int = 12) -> None:
    # The detail text is already in the DOM for normal Indeed listings.
    # Avoid repeated inner_text(timeout=2000) calls while scrolling:
    # this previously consumed about 26s per verified job in live captures.
    # A single DOM-side query/scroll is enough to trigger lazy content.
    try:
        panel.evaluate(
            """element => {
                const description = element.querySelector(
                    '#jobDescriptionText, [data-testid="jobsearch-jobDescriptionText"], '
                    + '[id^="jobDescriptionText"]'
                );
                if (description) {
                    description.scrollIntoView({block: 'nearest'});
                }
            }"""
        )
    except Exception:
        pass


def _parse_panel_text(text: str, expected_title: str) -> tuple[str, str, str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return expected_title, "", "", ""

    title = expected_title
    company = ""
    location = ""
    description = ""

    normalized_expected = " ".join(expected_title.split()).casefold()
    title_index = 0
    for index, line in enumerate(lines[:20]):
        normalized_line = " ".join(line.split()).casefold()
        if normalized_expected and (
            normalized_expected in normalized_line or normalized_line in normalized_expected
        ):
            title = line
            title_index = index
            break

    after_title = lines[title_index + 1 : title_index + 8]
    if after_title:
        company = after_title[0]
    if len(after_title) > 1:
        location = after_title[1]

    description_markers = (
        "descripción completa del empleo",
        "descripcion completa del empleo",
        "job description",
        "full job description",
    )
    for index, line in enumerate(lines):
        if any(marker in line.casefold() for marker in description_markers):
            description = "\n".join(lines[index + 1 :]).strip()
            break

    return title, company, location, description


def _listing_header_metadata(page: Page, source_job_id: str) -> tuple[str, str]:
    """Read company/location from the selected Indeed result card, not prose."""
    values = page.evaluate(
        """jobKey => {
            const nodes = Array.from(document.querySelectorAll('[data-jk]'));
            const match = nodes.find(node => node.getAttribute('data-jk') === jobKey);
            if (!match) return ['', ''];
            const card = match.closest('.job_seen_beacon, .cardOutline, li, [data-testid="slider_item"]')
                || match.parentElement?.parentElement?.parentElement;
            if (!card) return ['', ''];
            const first = selectors => {
                for (const selector of selectors) {
                    const node = card.querySelector(selector);
                    const value = (node?.innerText || node?.textContent || '').trim();
                    if (value) return value.replace(/\\s+/g, ' ');
                }
                return '';
            };
            return [
                first(['[data-testid="company-name"]', '.companyName', '[data-testid="companyName"]']),
                first(['[data-testid="text-location"]', '.companyLocation',
                       '[data-testid="job-location"]'])
            ];
        }""",
        source_job_id,
    )
    return tuple(values)


def _detail_fields(
    page: Page, expected_id: str, expected_title: str
) -> tuple[str, str, str, str, bool, str]:
    current_id = extract_indeed_job_key(page.url)
    data = _jobposting_jsonld(page)

    title = str(data.get("title", "") or "").strip()
    company = ""
    organization = data.get("hiringOrganization")
    if isinstance(organization, dict):
        company = str(organization.get("name", "") or "").strip()
    location = _location_from_jsonld(data)
    description = _strip_html(str(data.get("description", "") or ""))

    panel = _panel_container(page, expected_title)

    if panel is not None:
        # The selected listing title is our strongest panel anchor. Indeed's internal
        # heading tags vary and may point at labels such as "Salario" or "Tipo de empleo".
        title = expected_title
        _scroll_panel_to_description(panel)

        if not company:
            for selector in (
                "[data-company-name='true']",
                "[data-testid='inlineHeader-companyName']",
                "[data-testid='jobsearch-CompanyInfoContainer'] a",
            ):
                value = _text(panel.locator(selector).first)
                if value:
                    company = value
                    break

        if not location:
            for selector in (
                "[data-testid='job-location']",
                "[data-testid='inlineHeader-companyLocation']",
                "[data-testid='jobsearch-JobInfoHeader-companyLocation']",
            ):
                value = _text(panel.locator(selector).first)
                if value:
                    location = value
                    break

        if not description:
            for selector in (
                "#jobDescriptionText",
                "[data-testid='jobsearch-jobDescriptionText']",
                "[id^='jobDescriptionText']",
            ):
                value = _text(panel.locator(selector).first)
                if value:
                    description = value
                    break

        # A generic paragraph immediately after the title is not authoritative
        # company/location evidence. The old fallback silently stored sentences
        # from the job description as structured metadata.
        if not description:
            _, _, _, parsed_description = _parse_panel_text(_raw_text(panel), expected_title)
            description = parsed_description

    if not title:
        title = expected_title
    if not company:
        company = _first_text(
            page,
            (
                "[data-company-name='true']",
                "[data-testid='inlineHeader-companyName']",
            ),
        )
    if not location:
        location = _first_text(
            page,
            (
                "[data-testid='job-location']",
                "[data-testid='inlineHeader-companyLocation']",
            ),
        )

    # The left result card commonly exposes company/location even when the
    # detail pane uses a different header layout. Use the exact job key to avoid
    # associating the previous listing's metadata with the current job.
    if not company or not location:
        try:
            card_company, card_location = _listing_header_metadata(page, expected_id)
            company = company or card_company
            location = location or card_location
        except Exception:
            pass

    # Treat placeholders as missing location rather than verified geography.
    if location.strip(" ·•-|").strip() == "":
        location = ""

    reasons: list[str] = []
    if not company:
        reasons.append("Indeed detail page contained no reliable company name.")
    if not location:
        # Location can be absent for remote postings, so retain captured evidence
        # but mark the record unverified rather than inventing a location.
        reasons.append("Indeed detail page contained no reliable job location.")
    if current_id != expected_id:
        reasons.append(
            f"Indeed detail job key {current_id or '<missing>'} does not match expected {expected_id}."
        )
    if expected_title and title and expected_title.casefold() != title.casefold():
        # Indeed sometimes decorates card titles. A containment match is still acceptable.
        left = " ".join(expected_title.split()).casefold()
        right = " ".join(title.split()).casefold()
        if left not in right and right not in left:
            reasons.append(
                f"Detail title '{title}' does not match listing title '{expected_title}'."
            )
    if not description:
        reasons.append("Indeed detail page contained no usable job description.")

    return title or expected_title, company, location, description, not reasons, " | ".join(reasons)


def _access_warning(page: Page) -> str | None:
    url = page.url.casefold()
    body = ""
    with contextlib.suppress(Exception):
        body = page.locator("body").inner_text(timeout=2_000).casefold()
    markers = (
        "captcha",
        "verify you are human",
        "unusual activity",
        "access denied",
        "too many requests",
    )
    if any(marker in url or marker in body for marker in markers):
        return "Indeed presented an access challenge or automation warning."
    return None


def build_submit_payload(
    cards: list[CapturedCard],
    search_url: str,
    max_jobs: int,
    pages: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "search_url": search_url,
        "requested_item_limit": max_jobs,
        "stop_reason": "requested_limit_reached"
        if len(cards) >= max_jobs
        else "visible_jobs_exhausted",
        "pages": pages or [],
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
    search_url: str,
    max_jobs: int,
    pages: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload = build_submit_payload(cards, search_url, max_jobs, pages)
    try:
        validated = IndeedLiveCaptureRequest.model_validate(payload)
        for item in validated.items:
            IndeedLiveCaptureItemRequest.model_validate(item)
    except ValidationError as exc:
        return {
            "submitted": False,
            "stage": "local_validation",
            "validation_errors": json.loads(exc.json(include_url=False)),
        }

    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/captures/indeed/live",
        data=json.dumps(validated.model_dump(mode="json")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            return {
                "submitted": False,
                "status_code": exc.code,
                "error": (
                    "Indeed capture endpoint was not found in the running JOLT backend. "
                    "Restart the backend after updating JOLT, then retry."
                ),
                "response": body,
            }
        return {
            "submitted": False,
            "status_code": exc.code,
            "error": body,
        }
    except Exception as exc:
        return {"submitted": False, "error": str(exc)}


def run_capture(
    *,
    search_url: str,
    api_url: str,
    profile_dir: Path,
    output_zip: Path,
    max_jobs: int,
    pause_for_login: bool,
) -> Path:
    staging_dir = Path(tempfile.mkdtemp(prefix="jolt_indeed_"))
    evidence_dir = staging_dir / "evidence"
    evidence_dir.mkdir(parents=True)
    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1440, "height": 1000},
            )
            page = context.pages[0] if context.pages else context.new_page()
            tracing = False
            try:
                context.tracing.start(screenshots=True, snapshots=True, sources=False)
                tracing = True
                page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
                warning = _access_warning(page)
                if warning:
                    raise RuntimeError(warning)
                page.screenshot(path=evidence_dir / "01_search_opened.png", full_page=False)

                if pause_for_login:
                    print("Indeed is open in a persistent local browser profile.")
                    print("Use the visible anonymous search page and apply the filters you want.")
                    print("Do not sign in during this capture POC.")
                    input("Press Enter to capture the currently visible Indeed jobs: ")

                effective_search_url = page.url
                candidates = _visible_listing_candidates(page, max_jobs)
                if not candidates:
                    raise RuntimeError(
                        "No visible Indeed job links with durable job keys were found."
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
                                "Indeed listing card could not be clicked.",
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
                        reason = (
                            "Indeed detail panel did not become stable after the listing click."
                        )
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
                            source_url,
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

                context.tracing.stop(path=evidence_dir / "playwright_trace.zip")
                tracing = False

                summary = {
                    "source": "indeed",
                    "search_url": effective_search_url,
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
                    json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8"
                )
                for card in cards:
                    if card.detail_html:
                        (evidence_dir / f"job_{card.source_job_id}.redacted.html").write_text(
                            redact_text(card.detail_html), encoding="utf-8"
                        )

                api_result = submit_capture(api_url, cards, effective_search_url, max_jobs)
                (staging_dir / "api_result.json").write_text(
                    json.dumps(api_result, indent=2, ensure_ascii=True), encoding="utf-8"
                )
                (staging_dir / "run.log").write_text(
                    redact_text(
                        "\n".join(
                            [
                                f"Captured {len(cards)} visible Indeed jobs.",
                                f"Verified {sum(card.identity_verified for card in cards)} detail pages.",
                                f"API result: {api_result.get('status', api_result.get('error', 'completed'))}",
                            ]
                        )
                    ),
                    encoding="utf-8",
                )
            finally:
                if tracing:
                    with contextlib.suppress(Exception):
                        context.tracing.stop(path=evidence_dir / "playwright_trace.zip")
                with contextlib.suppress(Exception):
                    context.close()

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
    parser = argparse.ArgumentParser(description="Run a bounded supervised Indeed capture POC.")
    parser.add_argument("--search-url", default=DEFAULT_SEARCH_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--max-jobs", type=int, default=5)
    parser.add_argument("--no-login-pause", action="store_true")
    args = parser.parse_args(argv)
    if args.max_jobs < 1 or args.max_jobs > 10:
        parser.error("--max-jobs must be between 1 and 10 for the Indeed POC.")
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
    print(f"Indeed capture package created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
