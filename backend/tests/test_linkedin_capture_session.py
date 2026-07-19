from pathlib import Path

from jolt.linkedin_capture import (
    RetryMetrics,
    _is_relevant_filter_label,
    build_submit_payload,
    extract_search_state,
)
from jolt.multipage_capture import PageEvidence
from jolt.supervised_capture import CapturedCard


def test_retry_metrics_are_isolated_per_capture_run() -> None:
    first = RetryMetrics(retry_attempted_count=1)
    second = RetryMetrics()

    assert first.retry_attempted_count == 1
    assert second.retry_attempted_count == 0
    assert second.recovered_after_retry_count == 0
    assert second.failed_after_retry_count == 0


def test_irrelevant_navigation_labels_are_not_capture_filters() -> None:
    assert _is_relevant_filter_label("Past 24 hours") is True
    assert _is_relevant_filter_label("  Remote  ") is True
    assert _is_relevant_filter_label("Following") is False
    assert _is_relevant_filter_label("Notifications") is False
    assert _is_relevant_filter_label("   ") is False


def test_search_state_uses_one_stable_url_snapshot() -> None:
    initial_url = (
        "https://www.linkedin.com/jobs/search/?keywords=support&f_TPR=r604800"
        "&f_WT=2&geoId=91000000"
    )
    later_url = "https://www.linkedin.com/jobs/search/?keywords=changed"

    class EmptyLocator:
        def count(self) -> int:
            return 0

    class ChangingUrlPage:
        def __init__(self) -> None:
            self.reads = 0

        @property
        def url(self) -> str:
            self.reads += 1
            return initial_url if self.reads == 1 else later_url

        def locator(self, selector: str) -> EmptyLocator:
            return EmptyLocator()

    page = ChangingUrlPage()
    state = extract_search_state(page)  # type: ignore[arg-type]

    assert page.reads == 1
    assert state["effective_url"] == initial_url
    assert state["keywords"] == "support"
    assert state["url_filter_parameters"] == {
        "f_TPR": ["r604800"],
        "f_WT": ["2"],
        "geoId": ["91000000"],
    }


def test_submit_payload_includes_exact_page_evidence() -> None:
    card = CapturedCard(
        source_job_id="123",
        source_url="https://www.linkedin.com/jobs/view/123",
        title="Support Engineer",
        company="Example",
        location="Remote",
        detail_html="<main>details</main>",
        description="Troubleshoot customer incidents.",
        identity_verified=True,
        verification_reason="",
    )
    page = PageEvidence(
        page_number=1,
        visible_job_ids=("123", "456"),
        matched_card_selector="li[data-occludable-job-id]",
        next_control_present=True,
        next_control_enabled=False,
    )

    payload = build_submit_payload(
        [card],
        [page],
        "https://www.linkedin.com/jobs/search/?keywords=support",
        requested_item_limit=10,
        stop_reason="next_page_disabled",
    )

    assert payload["pages"] == [
        {
            "page_number": 1,
            "visible_job_ids": ["123", "456"],
            "next_control_present": True,
            "next_control_enabled": False,
        }
    ]
    assert payload["items"][0]["source_job_id"] == "123"
    assert "detail_html" not in payload["items"][0]


def test_runtime_entry_point_has_no_monkey_patching_or_zip_rewrite() -> None:
    repository = Path(__file__).resolve().parents[2]
    source = (repository / "backend" / "src" / "jolt" / "linkedin_capture.py").read_text(
        encoding="utf-8"
    )
    windows_entry = (
        repository / "backend" / "src" / "jolt" / "windows_console_capture.py"
    ).read_text(encoding="utf-8")

    assert "multipage_capture.capture_page_cards =" not in source
    assert "multipage_capture.capture_pages =" not in source
    assert "multipage_capture.submit_capture =" not in source
    assert "zipfile.ZipFile" not in source
    assert "capture_runtime_enhancements" not in windows_entry
    assert "return linkedin_capture.main()" in windows_entry
    assert not (
        repository / "backend" / "src" / "jolt" / "capture_runtime_enhancements.py"
    ).exists()
