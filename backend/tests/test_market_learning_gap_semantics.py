from jolt.market_intelligence import _assessment_gap_skill_labels


def test_gap_skill_extraction_uses_label_and_matched_terms_only() -> None:
    payload = {
        "gaps": [
            {
                "capability_id": "cloud",
                "label": "Azure cloud administration",
                "evidence_level": 2,
                "gap_type": "preparable_in_1_to_2_weeks",
                "matched_terms": ["Azure"],
                "preparation_topics": [
                    "Linux troubleshooting",
                    "AWS interview preparation",
                ],
            }
        ]
    }

    labels = _assessment_gap_skill_labels(payload)

    assert "Azure" in labels
    assert "Linux" not in labels
    assert "AWS" not in labels


def test_gap_skill_extraction_supports_legacy_string_gap() -> None:
    payload = {
        "gaps": [
            "SQL database troubleshooting gap",
        ]
    }

    labels = _assessment_gap_skill_labels(payload)

    assert "SQL" in labels
