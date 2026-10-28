from __future__ import annotations

from unittest.mock import MagicMock

from jolt.capture_processing_audit import audit_market_capture_coverage


def test_market_capture_coverage_reports_missing_and_unexpected() -> None:
    session = MagicMock()
    session.scalars.return_value.all.return_value = ["run-1", "run-2", "run-3"]
    session.execute.side_effect = [
        MagicMock(all=lambda: [
            ("run-1", "job-a"),
            ("run-1", "job-b"),
            ("run-2", "job-c"),
        ]),
        MagicMock(all=lambda: [
            ("run-1", "job-a"),
            ("run-2", "job-c"),
            ("run-2", "orphan"),
        ]),
    ]

    result = audit_market_capture_coverage(session)

    assert [(r.capture_run_id, r.expected, r.observed, r.missing, r.unexpected, r.complete) for r in result] == [
        ("run-1", 2, 1, 1, 0, False),
        ("run-2", 1, 2, 0, 1, False),
        ("run-3", 0, 0, 0, 0, True),
    ]
    assert session.execute.call_count == 2
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.delete.assert_not_called()
