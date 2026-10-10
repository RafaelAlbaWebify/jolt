from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from jolt.jobgether_preview import preview_jobs


def test_preview_rejects_unbounded_results() -> None:
    with pytest.raises(ValueError, match="1..25"):
        preview_jobs(keyword="support", limit=26)


def test_preview_reads_official_json_without_writing() -> None:
    payload = {"jobs": [{"title": "IT Support", "company": "Example", "url": "https://jobgether.com/job/example", "postedAt": "2026-10-10"}]}
    response = io.BytesIO(json.dumps(payload).encode())
    with patch("jolt.jobgether_preview.urllib.request.urlopen", return_value=response) as urlopen:
        result = preview_jobs(keyword="IT support", limit=3)
    assert result["count"] == 1
    assert result["jobs"][0]["title"] == "IT Support"
    assert "locations=spain" in urlopen.call_args.args[0].full_url


def test_preview_fails_closed_on_schema_change() -> None:
    with (
        patch("jolt.jobgether_preview.urllib.request.urlopen", return_value=io.BytesIO(b"{}")),
        pytest.raises(ValueError, match="schema"),
    ):
        preview_jobs(keyword="support")
