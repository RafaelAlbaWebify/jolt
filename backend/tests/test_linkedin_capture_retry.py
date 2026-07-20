from __future__ import annotations

from types import SimpleNamespace

from playwright.sync_api import TimeoutError

from jolt.linkedin_capture import RetryMetrics, _click_with_one_retry


class _FakeLink:
    def __init__(self, outcomes: list[Exception | None]) -> None:
        self._outcomes = iter(outcomes)
        self.click_count = 0

    def click(self, *, timeout: int) -> None:
        assert timeout == 8_000
        self.click_count += 1
        outcome = next(self._outcomes)
        if outcome is not None:
            raise outcome


class _FakeCard:
    def __init__(self) -> None:
        self.scroll_count = 0

    def scroll_into_view_if_needed(self, *, timeout: int) -> None:
        assert timeout == 2_000
        self.scroll_count += 1


def test_click_retry_recovers_on_second_attempt(monkeypatch) -> None:
    link = _FakeLink([TimeoutError("first click timed out"), None])
    card = _FakeCard()
    metrics = RetryMetrics()
    monkeypatch.setattr(
        "jolt.linkedin_capture.multipage_capture._title_link",
        lambda current_card: link,
    )

    result = _click_with_one_retry(link, card, metrics)  # type: ignore[arg-type]

    assert result is True
    assert link.click_count == 2
    assert card.scroll_count == 1
    assert metrics.retry_attempted_count == 1
    assert metrics.recovered_after_retry_count == 1
    assert metrics.failed_after_retry_count == 0


def test_click_retry_failure_is_counted_once(monkeypatch) -> None:
    link = _FakeLink(
        [
            TimeoutError("first click timed out"),
            TimeoutError("second click timed out"),
        ]
    )
    card = _FakeCard()
    metrics = RetryMetrics()
    monkeypatch.setattr(
        "jolt.linkedin_capture.multipage_capture._title_link",
        lambda current_card: SimpleNamespace(click=link.click),
    )

    result = _click_with_one_retry(link, card, metrics)  # type: ignore[arg-type]

    assert result is False
    assert link.click_count == 2
    assert card.scroll_count == 1
    assert metrics.retry_attempted_count == 1
    assert metrics.recovered_after_retry_count == 0
    assert metrics.failed_after_retry_count == 1
