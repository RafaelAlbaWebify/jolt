import json
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Any

from jolt.linkedin_capture import (
    RetryMetrics,
    _is_relevant_filter_label,
    build_submit_payload,
    capture_pages,
    extract_search_state,
    submit_capture,
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
        "https://www.linkedin.com/jobs/search/?keywords=support&f_TPR=r604800&f_WT=2&geoId=91000000"
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


def test_search_state_uses_caller_url_snapshot_without_rereading_page() -> None:
    snapshot = "https://www.linkedin.com/jobs/search/?keywords=support&f_TPR=r604800&f_WT=2"

    class EmptyLocator:
        def count(self) -> int:
            return 0

    class SnapshotPage:
        @property
        def url(self) -> str:
            raise AssertionError("The page URL must not be read again.")

        def locator(self, selector: str) -> EmptyLocator:
            return EmptyLocator()

    state = extract_search_state(
        SnapshotPage(),  # type: ignore[arg-type]
        effective_url=snapshot,
    )

    assert state["effective_url"] == snapshot
    assert state["keywords"] == "support"
    assert state["url_filter_parameters"] == {
        "f_TPR": ["r604800"],
        "f_WT": ["2"],
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


def test_capture_pages_reconciles_virtualized_ids(
    monkeypatch,
    tmp_path: Path,
) -> None:
    cards = object()

    class FakePage:
        def screenshot(self, **kwargs: Any) -> None:
            return None

    page_cards = [
        CapturedCard(
            source_job_id="1001",
            source_url="https://www.linkedin.com/jobs/view/1001",
            title="First",
            company="Example",
            location="Remote",
            detail_html="<main>First</main>",
            description="Detailed first support role description.",
            identity_verified=True,
            verification_reason="",
        ),
        CapturedCard(
            source_job_id="1003",
            source_url="https://www.linkedin.com/jobs/view/1003",
            title="Virtualized replacement",
            company="Example",
            location="Remote",
            detail_html="<main>Replacement</main>",
            description="Detailed replacement support role description.",
            identity_verified=True,
            verification_reason="",
        ),
    ]

    monkeypatch.setattr(
        "jolt.linkedin_capture.multipage_capture._wait_for_cards",
        lambda page: (cards, "virtualized-selector"),
    )
    monkeypatch.setattr(
        "jolt.linkedin_capture.multipage_capture._visible_job_ids",
        lambda cards: ("1001", "1002"),
    )
    monkeypatch.setattr(
        "jolt.linkedin_capture.multipage_capture._next_control",
        lambda page, next_page: (None, False, False),
    )
    monkeypatch.setattr(
        "jolt.linkedin_capture.capture_page_cards",
        lambda *args, **kwargs: page_cards,
    )

    captured, pages, skipped, stop_reason = capture_pages(
        FakePage(),  # type: ignore[arg-type]
        max_jobs=2,
        max_pages=1,
        evidence_dir=tmp_path,
        metrics=RetryMetrics(),
    )

    assert [card.source_job_id for card in captured] == ["1001", "1003"]
    assert pages[0].visible_job_ids == ("1001", "1002", "1003")
    assert skipped == []
    assert stop_reason == "requested_limit_reached"


def test_submit_capture_isolates_invalid_item(monkeypatch) -> None:
    valid = CapturedCard(
        source_job_id="123",
        source_url="https://www.linkedin.com/jobs/view/123",
        title="Support Engineer",
        company="Example",
        location="Remote",
        detail_html="<main>details</main>",
        description="Troubleshoot customer incidents and integrations.",
        identity_verified=True,
        verification_reason="",
    )
    invalid = CapturedCard(
        source_job_id="   ",
        source_url="",
        title="Malformed",
        company="Example",
        location="Remote",
        detail_html="",
        description="",
        identity_verified=False,
        verification_reason="Synthetic malformed record.",
    )
    page = PageEvidence(
        page_number=1,
        visible_job_ids=("123",),
        matched_card_selector="fixture",
        next_control_present=False,
        next_control_enabled=False,
    )

    submitted_payload: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self) -> bytes:
            return b'{"status":"completed"}'

    def fake_urlopen(request, timeout):
        submitted_payload.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr(
        "jolt.linkedin_capture.urllib.request.urlopen",
        fake_urlopen,
    )

    result = submit_capture(
        "http://127.0.0.1:8000",
        [valid, invalid],
        [page],
        "https://www.linkedin.com/jobs/search/",
        requested_item_limit=2,
        stop_reason="requested_limit_reached",
    )

    submitted_items = submitted_payload["items"]

    assert isinstance(submitted_items, list)
    assert [item["source_job_id"] for item in submitted_items] == ["123"]
    assert result["status"] == "completed"
    assert result["client_rejected_items"][0]["item_index"] == 1
    assert result["client_rejected_items"][0]["source_job_id"] == "   "


def test_submit_capture_preserves_http_validation_detail(monkeypatch) -> None:
    card = CapturedCard(
        source_job_id="123",
        source_url="https://www.linkedin.com/jobs/view/123",
        title="Support Engineer",
        company="Example",
        location="Remote",
        detail_html="<main>details</main>",
        description="Troubleshoot customer incidents and integrations.",
        identity_verified=True,
        verification_reason="",
    )
    page = PageEvidence(
        page_number=1,
        visible_job_ids=("123",),
        matched_card_selector="fixture",
        next_control_present=False,
        next_control_enabled=False,
    )
    detail = {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body", "items"],
                "msg": "Synthetic validation failure",
            }
        ]
    }

    def fail_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            422,
            "Unprocessable Entity",
            hdrs=None,
            fp=BytesIO(json.dumps(detail).encode("utf-8")),
        )

    monkeypatch.setattr(
        "jolt.linkedin_capture.urllib.request.urlopen",
        fail_urlopen,
    )

    result = submit_capture(
        "http://127.0.0.1:8000",
        [card],
        [page],
        "https://www.linkedin.com/jobs/search/",
        requested_item_limit=1,
        stop_reason="requested_limit_reached",
    )

    assert result["submitted"] is False
    assert result["status_code"] == 422
    assert result["response"] == detail


def test_submit_capture_reports_structural_validation_before_http(
    monkeypatch,
) -> None:
    card = CapturedCard(
        source_job_id="123",
        source_url="https://www.linkedin.com/jobs/view/123",
        title="Support Engineer",
        company="Example",
        location="Remote",
        detail_html="<main>details</main>",
        description="Troubleshoot customer incidents and integrations.",
        identity_verified=True,
        verification_reason="",
    )
    invalid_page = PageEvidence(
        page_number=2,
        visible_job_ids=("123",),
        matched_card_selector="fixture",
        next_control_present=False,
        next_control_enabled=False,
    )

    def unexpected_urlopen(request, timeout):
        raise AssertionError("Structurally invalid payload must not be submitted.")

    monkeypatch.setattr(
        "jolt.linkedin_capture.urllib.request.urlopen",
        unexpected_urlopen,
    )

    result = submit_capture(
        "http://127.0.0.1:8000",
        [card],
        [invalid_page],
        "https://www.linkedin.com/jobs/search/",
        requested_item_limit=1,
        stop_reason="requested_limit_reached",
    )

    assert result["submitted"] is False
    assert result["stage"] == "local_validation"
    assert result["validation_errors"]


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
