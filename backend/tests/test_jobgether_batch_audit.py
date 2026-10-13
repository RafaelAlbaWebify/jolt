import json

from jolt.jobgether_batch_audit import audit_batch, load_previous_reports

FIRST = "https://jobgether.com/offer/aaaaaaaaaaaaaaaaaaaaaaaa-first"
SECOND = "https://jobgether.com/offer/bbbbbbbbbbbbbbbbbbbbbbbb-second"


def _offer(url: str, structured: str = "", countries: list[str] | None = None) -> dict:
    return {
        "source_job_id": url.split("/offer/")[1][:24],
        "url": url,
        "status": "extracted_unverified",
        "structured_identifier": structured,
        "applicant_countries": countries or ["ES"],
        "spain_declared": True,
    }


def test_audit_repeat_and_shared_identifier() -> None:
    result = audit_batch(
        {"offers": [_offer(FIRST, "same"), _offer(SECOND, "same")]},
        [{"offers": [_offer(FIRST)]}],
    )
    assert result["seen_in_previous_reports"] == 1
    assert result["not_seen_in_available_reports"] == 1
    assert result["jobs"][0]["history_status"] == "seen_in_previous_report"
    assert "shared_structured_identifier" in result["jobs"][1]["warnings"]
    assert result["jobs"][0]["work_from_spain_verified"] is False


def test_audit_catches_broad_geography_and_invalid_identity() -> None:
    bad = _offer(FIRST, countries=[str(x) for x in range(110)])
    bad["source_job_id"] = "untrusted"
    result = audit_batch({"offers": [bad]}, [])
    assert result["jobs"][0]["history_status"] == "identity_unresolved"
    assert "overbroad_country_metadata" in result["jobs"][0]["warnings"]


def test_history_reader_ignores_corrupt_unrelated_and_current(tmp_path) -> None:
    good = tmp_path / "JOLT_JOBGETHER_BATCH_20261013_010000.json"
    good.write_text(json.dumps({"source": "jobgether", "offers": [_offer(FIRST)]}))
    (tmp_path / "JOLT_JOBGETHER_BATCH_bad.json").write_text("invalid JSON")
    current = tmp_path / "JOLT_JOBGETHER_BATCH_20261013_020000.json"
    current.write_text(json.dumps({"source": "jobgether", "offers": [_offer(SECOND)]}))
    (tmp_path / "unrelated.json").write_text("{}")
    reports = load_previous_reports(tmp_path, current_output=current)
    assert len(reports) == 1
    assert reports[0]["offers"][0]["url"] == FIRST
