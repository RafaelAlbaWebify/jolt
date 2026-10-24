"""Regression for recoverable Indeed checkpoints and login interstitial detection."""

from __future__ import annotations

import json
from types import SimpleNamespace

from jolt.indeed_chrome_attach import _indeed_login_visible, _save_partial_checkpoint
from jolt.supervised_capture import CapturedCard


def test_checkpoint_preserves_full_verified_payload_without_submission(tmp_path):
    card = CapturedCard(
        "job-123",
        "https://es.indeed.com/viewjob?jk=job-123",
        "Support Engineer",
        "Example Company",
        "España",
        "<html>private page</html>",
        "Full job description retained for recovery.",
        True,
        "",
        result_position=1,
        page_number=1,
        card_index=0,
    )
    pages = [{"page_number": 1, "visible_job_ids": ["job-123"]}]
    _save_partial_checkpoint(tmp_path, [card], pages, stop_reason="interrupted_before_submission")
    checkpoint = json.loads((tmp_path / "partial_checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["contract"] == "jolt-indeed-partial-checkpoint-v1"
    assert checkpoint["status"] == "partial_unsubmitted"
    assert checkpoint["captured_count"] == 1
    assert checkpoint["verified_count"] == 1
    assert checkpoint["items"][0]["description"] == card.description
    assert checkpoint["items"][0]["source_job_id"] == "job-123"
    assert checkpoint["pages"] == pages
    assert not (tmp_path / "api_result.json").exists()
    assert not (tmp_path / "partial_checkpoint.json.tmp").exists()


def test_login_detection_based_on_url_or_title():
    assert _indeed_login_visible(
        SimpleNamespace(url="https://secure.indeed.com/account/login", title=lambda: "")
    )
    assert _indeed_login_visible(
        SimpleNamespace(
            url="https://es.indeed.com/jobs?q=it", title=lambda: "Iniciar sesión | Cuentas Indeed"
        )
    )
    assert not _indeed_login_visible(
        SimpleNamespace(url="https://es.indeed.com/jobs?q=it", title=lambda: "IT Support - Indeed")
    )
