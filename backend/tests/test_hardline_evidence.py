from jolt.hardline_evidence import analyze_location_evidence


def test_explicit_spain_workplace_in_body_is_eligible_when_card_location_is_noise() -> None:
    result = analyze_location_evidence(
        location="Effective April 1, 2026, Toyota Automated Logistics brings together brands.",
        source_text=(
            "We are seeking an experienced Project Leader Engineering to join our team "
            "in Barcelona, Spain. In this role, you will lead multidisciplinary projects."
        ),
    )

    assert result.location_eligibility == "eligible"
    assert result.hardline_reject is False
    assert any("Barcelona, Spain" in item for item in result.positive_evidence)


def test_generic_spain_company_reference_does_not_become_workplace_evidence() -> None:
    result = analyze_location_evidence(
        location="Remote",
        source_text=(
            "Our company has customers in Barcelona, Spain and offices around the world. "
            "This remote role does not state its hiring territory."
        ),
    )

    assert result.location_eligibility == "conditional"
    assert result.hardline_reject is False
