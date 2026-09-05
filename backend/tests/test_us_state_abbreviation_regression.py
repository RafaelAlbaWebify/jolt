from __future__ import annotations

from jolt.hardline_evidence import analyze_location_evidence


def test_lowercase_de_in_foreign_location_metadata_is_not_delaware() -> None:
    result = analyze_location_evidence(
        location=(
            "Italy · 2 days ago · Promoted by hirer · Responses managed off LinkedIn · "
            "support de clientes"
        ),
        source_text="Technical Support Europe - Immunoassay",
    )

    assert result.hardline_reject is False
    assert "de" not in result.negative_evidence


def test_common_lowercase_state_abbreviation_words_do_not_trigger_us_state_hardline() -> None:
    for ordinary_word in ("de", "in", "or", "me"):
        result = analyze_location_evidence(
            location=f"Italy · remote · {ordinary_word}",
            source_text="European technical support role.",
        )

        assert result.hardline_reject is False, ordinary_word
        assert ordinary_word not in result.negative_evidence


def test_uppercase_us_state_abbreviation_after_city_comma_remains_hardline() -> None:
    result = analyze_location_evidence(
        location="Frederick, MD",
        source_text="IT Support Specialist",
    )

    assert result.location_eligibility == "ineligible"
    assert result.hardline_reject is True
    assert "MD" in result.negative_evidence


def test_full_us_state_name_remains_hardline() -> None:
    result = analyze_location_evidence(
        location="Austin, Texas",
        source_text="IT Support Specialist",
    )

    assert result.location_eligibility == "ineligible"
    assert result.hardline_reject is True
    assert any("Texas" in evidence for evidence in result.negative_evidence)


def test_explicit_uppercase_state_residency_remains_hardline() -> None:
    result = analyze_location_evidence(
        location="Remote",
        source_text="Candidates must reside in TX for this remote role.",
    )

    assert result.location_eligibility == "ineligible"
    assert result.hardline_reject is True
    assert any("TX" in evidence for evidence in result.negative_evidence)
