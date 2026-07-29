from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from types import TracebackType

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from sqlalchemy.orm import Session

from jolt.professional_intelligence_capture_runs import (
    ProfessionalCaptureOptions,
    ProfessionalCaptureRunResponse,
    get_professional_capture_run,
)
from jolt.professional_intelligence_records import ProfessionalCaptureRun
from jolt.professional_intelligence_supervised_capture import (
    CapturedProfessionalPage,
    start_professional_supervised_capture,
)

_ITEM_SELECTORS = (
    "[data-job-id]",
    "li.jobs-search-results__list-item",
    ".reusable-search__result-container",
    "article",
)
_AUTHWALL_URL_PARTS = (
    "/authwall",
    "/signup",
    "/login",
)
_AUTHWALL_TEXT_MARKERS = (
    "Join LinkedIn",
    "Already on Linkedin? Sign in",
    "Agree & Join",
    "LinkedIn is better on the app",
)


def _browser_profile_dir() -> Path:
    return Path("data") / "professional-browser-profile"


def _looks_like_linkedin_authwall(url: str, title: str, visible_text: str) -> bool:
    lowered_url = url.lower()
    if "linkedin.com" in lowered_url and any(part in lowered_url for part in _AUTHWALL_URL_PARTS):
        return True
    if title.strip().lower() in {"sign up | linkedin", "linkedin login, sign in | linkedin"}:
        return True
    return sum(marker in visible_text for marker in _AUTHWALL_TEXT_MARKERS) >= 2


class BoundedVisibleCaptureSession:
    def __init__(
        self,
        session: Session,
        run_id: str,
        options: ProfessionalCaptureOptions,
    ) -> None:
        self.session = session
        self.run_id = run_id
        self.options = options
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.browser_failed = False
        self.failure_detail = ""
        self.profile_dir = _browser_profile_dir()

    def __enter__(self) -> BoundedVisibleCaptureSession:
        self.playwright = sync_playwright().start()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.context = self.playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            headless=False,
            viewport={"width": 1400, "height": 950},
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.context is not None:
            with suppress(Exception):
                self.context.close()
        if self.playwright is not None:
            with suppress(Exception):
                self.playwright.stop()

    def _request_stop_after_failure(self, detail: str) -> None:
        self.browser_failed = True
        self.failure_detail = detail
        if not self.options.stop_on_failure:
            return
        run = self.session.get(ProfessionalCaptureRun, self.run_id)
        if run is not None:
            run.cancel_requested = True

    def _bounded_items(self, page: Page) -> tuple[int, str | None]:
        for selector in _ITEM_SELECTORS:
            locator = page.locator(selector)
            count = locator.count()
            if count == 0:
                continue
            maximum = self.options.max_items_per_source
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

    def _visible_text(self, page: Page, timeout_ms: int) -> str:
        return page.locator("body").inner_text(timeout=timeout_ms)

    def _wait_for_manual_linkedin_sign_in(self, page: Page, timeout_ms: int) -> None:
        deadline = max(timeout_ms, 120_000)
        elapsed = 0
        while elapsed < deadline:
            page.wait_for_timeout(1_000)
            elapsed += 1_000
            visible_text = self._visible_text(page, min(timeout_ms, 5_000))
            if not _looks_like_linkedin_authwall(page.url, page.title(), visible_text):
                return
        raise RuntimeError(
            "LinkedIn authentication is required. JOLT opened a persistent visible browser profile; "
            "sign in to LinkedIn in that browser, then run the bounded capture again."
        )

    def __call__(self, url: str) -> CapturedProfessionalPage:
        if self.browser_failed:
            raise RuntimeError(
                "The capture browser already failed; JOLT will not relaunch it in this run."
            )
        if self.context is None:
            raise RuntimeError("The bounded capture browser context is not available.")

        page: Page | None = None
        try:
            page = self.context.new_page()
            timeout_ms = self.options.timeout_seconds * 1_000
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            network_idle = True
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5_000))
            except Exception:
                network_idle = False

            visible_text = self._visible_text(page, timeout_ms)
            if _looks_like_linkedin_authwall(page.url, page.title(), visible_text):
                self._wait_for_manual_linkedin_sign_in(page, timeout_ms)
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5_000))
                    network_idle = True
                except Exception:
                    network_idle = False
                visible_text = self._visible_text(page, timeout_ms)
                if _looks_like_linkedin_authwall(page.url, page.title(), visible_text):
                    raise RuntimeError(
                        "LinkedIn still shows an authentication wall after manual sign-in wait. "
                        "Run the capture again after confirming the persistent browser is signed in."
                    )

            detected_items = 0
            item_selector: str | None = None
            for _ in range(self.options.max_scroll_batches):
                detected_items, item_selector = self._bounded_items(page)
                if detected_items >= self.options.max_items_per_source:
                    break
                before_height = page.evaluate("document.body.scrollHeight")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
                after_height = page.evaluate("document.body.scrollHeight")
                if after_height == before_height:
                    break

            detected_items, item_selector = self._bounded_items(page)
            visible_text = self._visible_text(page, timeout_ms)
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
                f"Applied {self.options.max_scroll_batches} maximum scroll batches, "
                f"{self.options.max_items_per_source} maximum items, and a "
                f"{self.options.timeout_seconds}-second timeout."
                f" Using persistent browser profile {self.profile_dir}.{item_detail}"
            )
            return CapturedProfessionalPage(
                screenshot_png=page.screenshot(full_page=True),
                visible_text=visible_text,
                title=page.title(),
                final_url=page.url,
                http_status=response.status if response is not None else None,
                readiness_status=readiness_status,
                readiness_detail=readiness_detail,
            )
        except Exception as exc:
            self._request_stop_after_failure(str(exc))
            raise
        finally:
            if page is not None:
                with suppress(Exception):
                    page.close()


def start_bounded_professional_capture(
    session: Session,
    run_id: str,
) -> ProfessionalCaptureRunResponse:
    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise LookupError(f"Professional capture run {run_id} was not found.")
    options = ProfessionalCaptureOptions.model_validate_json(run.capture_options_json)

    with BoundedVisibleCaptureSession(session, run_id, options) as capture_session:
        response = start_professional_supervised_capture(
            session,
            run_id,
            capture_source=capture_session,
        )

    if capture_session.browser_failed and options.stop_on_failure:
        run = session.get(ProfessionalCaptureRun, run_id)
        if run is not None and run.status == "cancelled":
            run.status = "failed"
            run.stop_reason = "stopped_after_first_source_failure"
            session.commit()
            response = get_professional_capture_run(session, run_id)
    return response
