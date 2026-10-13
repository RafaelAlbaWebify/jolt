from unittest.mock import patch

from jolt.jobgether_detail_probe import main

URL = "https://jobgether.com/offer/6ac5d9628a27695aea363d32-support-technician"


def test_probe_reports_structured_details_without_full_description(capsys) -> None:
    result = {
        "source_job_id": "6ac5d9628a27695aea363d32",
        "status": "structured_detail_present",
        "description": "secret job description",
        "source_evidence_verified": False,
    }
    with (
        patch("sys.argv", ["probe", "--url", URL]),
        patch("jolt.jobgether_detail_probe.fetch_jobgether_detail", return_value=result),
    ):
        status = main()
    assert status == 0
    printed = capsys.readouterr().out
    assert '"description_length": 22' in printed
    assert "secret job description" not in printed
    assert '"source_evidence_verified": false' in printed


def test_probe_returns_unresolved_without_database_access(capsys) -> None:
    with (
        patch("sys.argv", ["probe", "--url", URL]),
        patch(
            "jolt.jobgether_detail_probe.fetch_jobgether_detail",
            return_value={"source_job_id": "6ac5d9628a27695aea363d32", "status": "unresolved"},
        ),
    ):
        assert main() == 2
    assert '"status": "unresolved"' in capsys.readouterr().out
