from __future__ import annotations

import pytest

from jolt.indeed_chrome_attach import _navigate_search_page, parse_args


def test_parse_args_defaults_to_bounded_capture(tmp_path) -> None:
    args = parse_args(["--output-zip", str(tmp_path / "capture.zip")])

    assert args.cdp_endpoint == "http://127.0.0.1:9222"
    assert args.api_url == "http://127.0.0.1:8000"
    assert args.max_jobs == 15
    assert args.max_pages == 1
    assert args.no_pause is False


def test_parse_args_rejects_more_than_one_hundred_jobs(tmp_path) -> None:
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--output-zip",
                str(tmp_path / "capture.zip"),
                "--max-jobs",
                "101",
            ]
        )


def test_parse_args_rejects_more_than_ten_pages(tmp_path) -> None:
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--output-zip",
                str(tmp_path / "capture.zip"),
                "--max-pages",
                "11",
            ]
        )


class _FakePage:
    def __init__(self, *, closed: bool = False) -> None:
        self._closed = closed
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
            "domcontentloaded",
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
            "domcontentloaded",
            60_000,
        )
    ]
