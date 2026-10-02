from __future__ import annotations

import pytest

from jolt.indeed_chrome_attach import parse_args


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
