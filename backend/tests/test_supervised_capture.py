from __future__ import annotations

import json
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from jolt.supervised_capture import (
    capture_visible_cards,
    extract_job_id,
    package_run,
    parse_args,
    redact_text,
)

FIXTURE = Path(__file__).parent / "fixtures" / "linkedin_search.html"


def test_redaction_and_job_identity_helpers() -> None:
    raw = (
        "Authorization: Bearer secret-token user@example.com +34 600 123 456 "
        "csrf='abcdef' https://www.linkedin.com/jobs/view/4434979232"
    )
    redacted = redact_text(raw)

    assert "secret-token" not in redacted
    assert "user@example.com" not in redacted
    assert "+34 600 123 456" not in redacted
    assert "abcdef" not in redacted
    assert extract_job_id(raw) == "4434979232"
    assert (
        extract_job_id("https://www.linkedin.com/jobs/search/?currentJobId=4435000001")
        == "4435000001"
    )


def test_bounded_browser_capture_verifies_fixture_details(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(FIXTURE.resolve().as_uri())
        cards = capture_visible_cards(page, max_jobs=2, evidence_dir=evidence_dir)
        browser.close()

    assert [card.source_job_id for card in cards] == ["4434979232", "4435000001"]
    assert all(card.identity_verified for card in cards)
    assert (evidence_dir / "job_4434979232.png").exists()
    assert (evidence_dir / "job_4435000001.png").exists()


def test_package_contains_only_relative_files(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "capture_summary.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    nested = staging / "evidence"
    nested.mkdir()
    (nested / "run.log").write_text("complete", encoding="utf-8")
    destination = tmp_path / "capture.zip"

    package_run(staging, destination)

    with zipfile.ZipFile(destination) as archive:
        assert archive.namelist() == ["capture_summary.json", "evidence/run.log"]


def test_cli_enforces_bounded_job_count(tmp_path: Path) -> None:
    args = parse_args(
        [
            "--profile-dir",
            str(tmp_path / "profile"),
            "--output-zip",
            str(tmp_path / "capture.zip"),
            "--max-jobs",
            "12",
        ]
    )
    assert args.max_jobs == 12
