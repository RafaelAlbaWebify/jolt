from __future__ import annotations

from unittest.mock import patch

from jolt.jobgether_capture_cli import run


def test_runner_default_is_read_only() -> None:
    sample = {"source": "jobgether", "count": 1, "jobs": [{"title": "IT Support"}]}
    with (
        patch("jolt.jobgether_capture_cli.preview_jobs", return_value=sample),
        patch("jolt.jobgether_capture_cli.create_session_factory") as factory,
    ):
        output = run(keyword="IT support", location="spain", limit=1, commit=False)
    assert output["committed"] is False
    assert output["triage"]["count"] == 1
    assert output["triage"]["ranked"][0]["priority"] == "review_later"
    assert output["triage"]["ranked"][0]["work_from_spain_verified"] is False
    factory.assert_not_called()
