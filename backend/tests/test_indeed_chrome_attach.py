from __future__ import annotations

import sqlite3

import pytest

from jolt.indeed_chrome_attach import (
    _navigate_search_page,
    _page_search_url,
    _verified_known_job_ids,
    parse_args,
)


def test_parse_args_defaults_to_bounded_capture(tmp_path) -> None:
    args = parse_args(["--output-zip", str(tmp_path / "capture.zip")])

    assert args.cdp_endpoint == "http://127.0.0.1:9222"
    assert args.api_url == "http://127.0.0.1:8000"
    assert args.search_url == ""
    assert args.max_jobs == 15
    assert args.max_pages == 1
    assert args.no_pause is False


def test_parse_args_rejects_more_than_two_hundred_jobs(tmp_path) -> None:
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--output-zip",
                str(tmp_path / "capture.zip"),
                "--max-jobs",
                "201",
            ]
        )


def test_parse_args_rejects_more_than_twenty_pages(tmp_path) -> None:
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--output-zip",
                str(tmp_path / "capture.zip"),
                "--max-pages",
                "21",
            ]
        )


class _FakePage:
    def __init__(self, *, closed: bool = False, url: str = "about:blank") -> None:
        self._closed = closed
        self.url = url
        self.goto_calls: list[tuple[str, str, int]] = []

    def is_closed(self) -> bool:
        return self._closed

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append((url, wait_until, timeout))


class _FakeContext:
    def __init__(self, replacement: _FakePage) -> None:
        self.replacement = replacement
        self.new_page_calls = 0

    def new_page(self) -> _FakePage:
        self.new_page_calls += 1
        return self.replacement


def test_navigate_search_page_replaces_closed_cdp_page() -> None:
    closed_page = _FakePage(closed=True)
    replacement = _FakePage()
    context = _FakeContext(replacement)

    selected = _navigate_search_page(
        context,  # type: ignore[arg-type]
        closed_page,  # type: ignore[arg-type]
        "https://es.indeed.com/jobs?q=IT+Support&start=10",
    )

    assert selected is replacement
    assert context.new_page_calls == 1
    assert replacement.goto_calls == [
        (
            "https://es.indeed.com/jobs?q=IT+Support&start=10",
            "commit",
            60_000,
        )
    ]


def test_navigate_search_page_reuses_open_cdp_page() -> None:
    open_page = _FakePage()
    replacement = _FakePage()
    context = _FakeContext(replacement)

    selected = _navigate_search_page(
        context,  # type: ignore[arg-type]
        open_page,  # type: ignore[arg-type]
        "https://es.indeed.com/jobs?q=application+support",
    )

    assert selected is open_page
    assert context.new_page_calls == 0
    assert open_page.goto_calls == [
        (
            "https://es.indeed.com/jobs?q=application+support",
            "commit",
            60_000,
        )
    ]


def test_indeed_verification_document_timeout_does_not_abort_capture() -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    target = "https://es.indeed.com/jobs?q=application+support&l=Espa%C3%B1a"
    page = _FakePage(url=target)
    replacement = _FakePage()
    context = _FakeContext(replacement)

    def timed_out(url: str, *, wait_until: str, timeout: int) -> None:
        page.goto_calls.append((url, wait_until, timeout))
        raise PlaywrightTimeoutError("Cloudflare verification pending")

    page.goto = timed_out  # type: ignore[method-assign]
    selected = _navigate_search_page(context, page, target)  # type: ignore[arg-type]
    assert selected is page
    assert context.new_page_calls == 0


def test_indeed_navigation_timeout_on_unrelated_page_fails_closed() -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    page = _FakePage(url="https://es.indeed.com/")
    context = _FakeContext(_FakePage())

    def timed_out(url: str, *, wait_until: str, timeout: int) -> None:
        raise PlaywrightTimeoutError("Navigation never committed")

    page.goto = timed_out  # type: ignore[method-assign]
    with pytest.raises(PlaywrightTimeoutError):
        _navigate_search_page(context, page, "https://es.indeed.com/jobs?q=application+support")  # type: ignore[arg-type]


def test_page_search_url_advances_indeed_pagination() -> None:
    base = "https://es.indeed.com/jobs?q=application+support&l=Espa%C3%B1a&vjk=abc"

    assert _page_search_url(base, 1) == (
        "https://es.indeed.com/jobs?q=application+support&l=Espa%C3%B1a"
    )
    assert _page_search_url(base, 2) == (
        "https://es.indeed.com/jobs?q=application+support&l=Espa%C3%B1a&start=10"
    )
    assert _page_search_url(base, 3) == (
        "https://es.indeed.com/jobs?q=application+support&l=Espa%C3%B1a&start=20"
    )


def test_page_search_url_replaces_stale_start_and_job_identity() -> None:
    current = "https://es.indeed.com/jobs?q=application+support&start=40&vjk=abc&jk=def"

    assert _page_search_url(current, 2) == (
        "https://es.indeed.com/jobs?q=application+support&start=10"
    )


def test_parse_args_accepts_explicit_search_url(tmp_path) -> None:
    url = "https://es.indeed.com/jobs?q=soporte&l=Vigo"
    args = parse_args(["--output-zip", str(tmp_path / "capture.zip"), "--search-url", url])
    assert args.search_url == url


def test_verified_known_ids_skips_when_no_database(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOLT_DATABASE_URL", "sqlite:///external.db")
    assert _verified_known_job_ids(["abc"]) == set()


def test_verified_known_ids_ignores_empty_input() -> None:
    assert _verified_known_job_ids([]) == set()


def test_verified_known_ids_only_returns_verified_indeed(tmp_path, monkeypatch) -> None:
    import jolt.indeed_chrome_attach as module

    fake_module = tmp_path / "backend" / "src" / "jolt" / "indeed_chrome_attach.py"
    fake_module.parent.mkdir(parents=True)
    db = tmp_path / "backend" / "data" / "jolt.db"
    db.parent.mkdir(parents=True)
    monkeypatch.delenv("JOLT_DATABASE_URL", raising=False)
    monkeypatch.setattr(module, "__file__", str(fake_module))
    with sqlite3.connect(db) as con:
        con.executescript(
            "CREATE TABLE capture_runs(id TEXT, source TEXT);"
            "CREATE TABLE capture_items("
            "source_job_id TEXT, capture_run_id TEXT, detail_status TEXT,"
            "source_document_id TEXT);"
            "INSERT INTO capture_runs VALUES ('a', 'indeed'), ('b', 'linkedin');"
            "INSERT INTO capture_items VALUES ('known', 'a', 'verified', 'doc');"
            "INSERT INTO capture_items VALUES ('unverified', 'a', 'rejected', NULL);"
            "INSERT INTO capture_items VALUES ('other', 'b', 'verified', 'doc');"
        )
    assert _verified_known_job_ids(["known", "unverified", "other"]) == {"known"}


def test_readiness_probe_observes_raw_dom_before_candidate_extraction(monkeypatch) -> None:
    import jolt.indeed_chrome_attach as module

    events: list[str] = []

    class Locator:
        def count(self) -> int:
            events.append("dom")
            return 4

    class Page:
        def locator(self, selector: str) -> Locator:
            assert selector == "[data-jk]"
            return Locator()

    def candidates(page: object, max_jobs: int) -> list[dict[str, str]]:
        events.append("candidates")
        assert max_jobs == 15
        return [{"source_job_id": "known"}]

    monkeypatch.setattr(module, "_visible_listing_candidates", candidates)
    diagnostics: dict[str, object] = {}
    actual = module._wait_for_visible_results(
        Page(),  # type: ignore[arg-type]
        15,
        readiness_diagnostics=diagnostics,
    )
    assert actual == [{"source_job_id": "known"}]
    assert events == ["dom", "candidates"]
    assert diagnostics["first_dom_listing_seconds"] is not None
    assert diagnostics["first_valid_candidate_seconds"] is not None
    assert diagnostics["raw_listing_marker_count"] == 4
    assert diagnostics["valid_candidate_count"] == 1
    assert diagnostics["poll_count"] == 1
    assert diagnostics["login_seen"] is False
    assert diagnostics["access_warning_seen"] is False


def test_readiness_probe_does_not_change_candidate_acceptance(monkeypatch) -> None:
    import jolt.indeed_chrome_attach as module

    class Page:
        def locator(self, selector: str) -> object:
            raise AssertionError("DOM probe must be optional")

    monkeypatch.setattr(
        module,
        "_visible_listing_candidates",
        lambda page, max_jobs: [{"source_job_id": "accepted"}],
    )
    assert module._wait_for_visible_results(Page(), 15) == [  # type: ignore[arg-type]
        {"source_job_id": "accepted"}
    ]


def test_indeed_checkpoint_is_atomic_recoverable_and_skips_existing_html(
    tmp_path, monkeypatch
) -> None:
    import json

    import jolt.indeed_chrome_attach as module
    from jolt.supervised_capture import CapturedCard

    card = CapturedCard(
        source_job_id="test-job",
        source_url="https://es.indeed.com/viewjob?jk=test-job",
        title="Test title",
        company="Test company",
        location="Remote",
        detail_html="<html>verified evidence</html>",
        description="Verified detail text",
        identity_verified=True,
        verification_reason="verified",
    )
    calls: list[str] = []
    original = module.redact_text

    def redaction_spy(value: str) -> str:
        calls.append(value)
        return original(value)

    monkeypatch.setattr(module, "redact_text", redaction_spy)
    module._save_partial_checkpoint(
        tmp_path, [card], [{"page_number": 1}], stop_reason="page_completed"
    )
    checkpoint = tmp_path / "partial_checkpoint.json"
    evidence = tmp_path / "evidence" / "job_test-job.redacted.html"
    first = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert first["items"][0]["description"] == "Verified detail text"
    assert first["status"] == "partial_unsubmitted"
    assert evidence.exists()
    assert len(calls) == 1
    assert not checkpoint.with_name(checkpoint.name + ".tmp").exists()

    module._save_partial_checkpoint(
        tmp_path, [card], [{"page_number": 1}], stop_reason="interrupted_before_submission"
    )
    second = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert second["stop_reason"] == "interrupted_before_submission"
    assert len(calls) == 1
