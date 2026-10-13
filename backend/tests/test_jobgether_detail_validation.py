from __future__ import annotations

from jolt.jobgether_detail_validation import validate_jobgether_detail


def test_matching_detail_is_structurally_valid_but_not_source_verified() -> None:
    identifier = "6ac85207480485773199660a"
    url = f"https://jobgether.com/offer/{identifier}-support-engineer"
    result = validate_jobgether_detail(
        observed_id=identifier,
        observed_url=url,
        detail_url=url,
        title="IT Support Engineer",
        company="Example",
        description="Provide support for production systems, resolve incidents, investigate errors, and coordinate escalations with other teams.",
    )
    assert result["identity_consistent"] is True
    assert result["source_evidence_verified"] is False
    assert result["work_from_spain_verified"] is False


def test_wrong_detail_identity_and_short_text_fail_closed() -> None:
    identifier = "6ac85207480485773199660a"
    result = validate_jobgether_detail(
        observed_id=identifier,
        observed_url=f"https://jobgether.com/offer/{identifier}-support",
        detail_url="https://untrusted.example/offer/6ac700878a27695aea3b995e-support",
        title="Support",
        company="",
        description="Short",
    )
    assert result["identity_consistent"] is False
    assert "detail_identity_mismatch" in result["reasons"]
    assert "missing_company" in result["reasons"]
    assert "insufficient_description" in result["reasons"]
