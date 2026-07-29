from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import suppress
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.professional_intelligence_capture_runs import (
    ProfessionalCaptureOptions,
    ProfessionalSourceProgress,
    effective_capture_run_status,
    get_professional_capture_run,
)
from jolt.professional_intelligence_records import ProfessionalCaptureRun
from jolt.professional_intelligence_sources import (
    ProfessionalIntelligenceSource,
    ProfessionalSourceCategory,
)
from jolt.professional_intelligence_supervised_capture import (
    CapturedProfessionalPage,
    start_professional_supervised_capture,
)

SessionProvider = Callable[[], Iterator[Session]]

_ITEM_SELECTORS = (
    "[data-job-id]",
    "li.jobs-search-results__list-item",
    ".jobs-search-results__list-item",
    ".job-card-container",
    ".reusable-search__result-container",
    "article",
)
_AUTHWALL_URL_PARTS = ("/authwall", "/signup", "/login")
_AUTHWALL_TEXT_MARKERS = (
    "Join LinkedIn",
    "Already on Linkedin? Sign in",
    "Agree & Join",
    "LinkedIn is better on the app",
)


def manual_browser_profile_dir() -> Path:
    return Path("data") / "professional-browser-profile"


def looks_like_linkedin_authwall(url: str, title: str, visible_text: str) -> bool:
    lowered_url = url.lower()
    if "linkedin.com" in lowered_url and any(part in lowered_url for part in _AUTHWALL_URL_PARTS):
        return True
    if title.strip().lower() in {"sign up | linkedin", "linkedin login, sign in | linkedin"}:
        return True
    return sum(marker in visible_text for marker in _AUTHWALL_TEXT_MARKERS) >= 2


def _close_session(session_iterator: Iterator[Session], session: Session | None) -> None:
    close = getattr(session_iterator, "close", None)
    if callable(close):
        with suppress(Exception):
            close()
    elif session is not None:
        with suppress(Exception):
            session.close()


def _visible_text(page: Page, timeout_ms: int) -> str:
    return page.locator("body").inner_text(timeout=timeout_ms)


def _bounded_items(page: Page, maximum: int) -> tuple[int, str | None]:
    for selector in _ITEM_SELECTORS:
        locator = page.locator(selector)
        count = locator.count()
        if count == 0:
            continue
        if count > maximum:
            page.evaluate(
                """([selector, maximum]) => {
                    const items = Array.from(document.querySelectorAll(selector));
                    for (const item of items.slice(maximum)) {
                        item.setAttribute('data-jolt-capture-excluded', 'true');
                        item.style.display = 'none';
                    }
                }""",
                [selector, maximum],
            )
        return min(count, maximum), selector
    return 0, None


def _prepared_page_capture(page: Page, options: ProfessionalCaptureOptions) -> CapturedProfessionalPage:
    timeout_ms = options.timeout_seconds * 1_000
    page.bring_to_front()
    network_idle = True
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5_000))
    except Exception:
        network_idle = False

    visible_text = _visible_text(page, timeout_ms)
    if looks_like_linkedin_authwall(page.url, page.title(), visible_text):
        raise RuntimeError(
            "The prepared LinkedIn browser page is still an authwall/sign-in page. "
            "Sign in and navigate to the exact LinkedIn profile or job-search results page, then capture again."
        )

    detected_items = 0
    item_selector: str | None = None
    for _ in range(options.max_scroll_batches):
        detected_items, item_selector = _bounded_items(page, options.max_items_per_source)
        if detected_items >= options.max_items_per_source:
            break
        before_height = page.evaluate("document.body.scrollHeight")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(500)
        after_height = page.evaluate("document.body.scrollHeight")
        if after_height == before_height:
            break

    detected_items, item_selector = _bounded_items(page, options.max_items_per_source)
    visible_text = _visible_text(page, timeout_ms)
    body_ready = len(visible_text.strip()) >= 100
    if network_idle and body_ready:
        readiness_status = "network_idle_and_body_ready"
    elif body_ready:
        readiness_status = "body_ready"
    else:
        readiness_status = "readiness_timeout"

    item_detail = (
        f" Detected {detected_items} bounded items using {item_selector}."
        if item_selector
        else " No repeated result-card selector was detected."
    )
    readiness_detail = (
        "Captured the already-open user-prepared Chromium page. "
        f"Applied {options.max_scroll_batches} maximum scroll batches, "
        f"{options.max_items_per_source} maximum items, and a "
        f"{options.timeout_seconds}-second timeout.{item_detail}"
    )
    return CapturedProfessionalPage(
        screenshot_png=page.screenshot(full_page=True),
        visible_text=visible_text,
        title=page.title(),
        final_url=page.url,
        http_status=None,
        readiness_status=readiness_status,
        readiness_detail=readiness_detail,
    )


def _prepared_source_for_page(page: Page) -> ProfessionalIntelligenceSource:
    label = "Prepared LinkedIn page"
    if "/jobs/" in page.url:
        label = "Prepared LinkedIn job search"
    elif "/in/" in page.url:
        label = "Prepared LinkedIn profile"
    return ProfessionalIntelligenceSource(
        source_id="linkedin-current-page",
        label=label,
        category=ProfessionalSourceCategory.CAREER,
        url=page.url if page.url.startswith("https://www.linkedin.com/") else "https://www.linkedin.com/",
        initial_scope=True,
    )


def _prepare_run_for_current_page(session: Session, run_id: str, page: Page) -> None:
    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise LookupError(f"Professional capture run {run_id} was not found.")
    if effective_capture_run_status(run) != "authorized":
        raise ValueError("A current explicit authorization is required before current-page capture.")
    source = _prepared_source_for_page(page)
    run.source_snapshot_json = json.dumps([source.model_dump(mode="json")])
    run.source_progress_json = json.dumps(
        [
            ProfessionalSourceProgress(
                source_id=source.source_id,
                status="pending",
                detail="Waiting to capture the user-prepared Chromium page.",
            ).model_dump(mode="json")
        ]
    )
    run.completed_source_count = 0
    run.current_source_id = ""
    run.stop_reason = "manual_browser_ready"
    run.progress_updated_at = utc_now()
    session.commit()


class ManualProfessionalBrowser:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._capture_requested = threading.Event()
        self._stop_requested = threading.Event()
        self._thread: threading.Thread | None = None
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._pending: tuple[SessionProvider, str] | None = None
        self._ready = False
        self._last_error = ""
        self._last_url = ""
        self._last_title = ""

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ready": self._ready,
                "current_url": self._last_url,
                "title": self._last_title,
                "last_error": self._last_error,
                "profile_dir": str(manual_browser_profile_dir()),
            }

    def open(self) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self.status()
            self._capture_requested.clear()
            self._stop_requested.clear()
            self._ready = False
            self._last_error = ""
            self._thread = threading.Thread(target=self._run, name="jolt-professional-manual-browser", daemon=True)
            self._thread.start()
        return self.status()

    def queue_capture(self, get_session: SessionProvider, run_id: str) -> dict[str, Any]:
        with self._lock:
            if not self._ready or self._page is None:
                raise RuntimeError("The manual Professional browser is not ready. Open it before capturing.")
            if self._pending is not None:
                raise RuntimeError("A manual current-page capture is already queued.")
            self._pending = (get_session, run_id)
            self._capture_requested.set()
        return self.status()

    def _run(self) -> None:
        try:
            self._playwright = sync_playwright().start()
            profile_dir = manual_browser_profile_dir()
            profile_dir.mkdir(parents=True, exist_ok=True)
            self._context = self._playwright.chromium.launch_persistent_context(
                str(profile_dir),
                headless=False,
                viewport={"width": 1400, "height": 950},
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded", timeout=45_000)
            self._sync_page_status()
            with self._lock:
                self._ready = True

            while not self._stop_requested.is_set():
                if not self._capture_requested.wait(timeout=0.5):
                    self._sync_page_status()
                    continue
                self._capture_requested.clear()
                with self._lock:
                    pending = self._pending
                    self._pending = None
                if pending is None:
                    continue
                get_session, run_id = pending
                self._capture_current_page(get_session, run_id)
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
                self._ready = False
        finally:
            with suppress(Exception):
                if self._context is not None:
                    self._context.close()
            with suppress(Exception):
                if self._playwright is not None:
                    self._playwright.stop()

    def _sync_page_status(self) -> None:
        if self._page is None:
            return
        with suppress(Exception):
            with self._lock:
                self._last_url = self._page.url
                self._last_title = self._page.title()

    def _capture_current_page(self, get_session: SessionProvider, run_id: str) -> None:
        if self._page is None:
            return
        session_iterator = get_session()
        session: Session | None = None
        try:
            session = next(session_iterator)
            _prepare_run_for_current_page(session, run_id, self._page)
            run = session.get(ProfessionalCaptureRun, run_id)
            if run is None:
                raise LookupError(f"Professional capture run {run_id} was not found.")
            options = ProfessionalCaptureOptions.model_validate_json(run.capture_options_json)
            start_professional_supervised_capture(
                session,
                run_id,
                capture_source=lambda _url: _prepared_page_capture(self._page, options),
            )
            self._sync_page_status()
        except Exception as exc:
            if session is not None:
                session.rollback()
                run = session.get(ProfessionalCaptureRun, run_id)
                if run is not None:
                    now = utc_now()
                    run.status = "failed"
                    run.completed_at = now
                    run.current_source_id = ""
                    run.progress_updated_at = now
                    run.stop_reason = "manual_current_page_capture_failure"
                    session.commit()
            with self._lock:
                self._last_error = str(exc)
        finally:
            _close_session(session_iterator, session)


manual_professional_browser = ManualProfessionalBrowser()


def open_manual_professional_browser() -> dict[str, Any]:
    return manual_professional_browser.open()


def manual_professional_browser_status() -> dict[str, Any]:
    return manual_professional_browser.status()


def queue_manual_current_page_capture(get_session: SessionProvider, run_id: str) -> dict[str, Any]:
    return manual_professional_browser.queue_capture(get_session, run_id)
