from collections import Counter

from jolt.market_intelligence import _learning_signal_rows


def test_learning_indicator_is_bounded_to_ten() -> None:
    rows = _learning_signal_rows(
        skills=Counter({"REST API": 1}),
        required_skills=Counter({"REST API": 1}),
        preferred_skills=Counter(),
        gap_skills=Counter({"REST API": 32}),
        capability_gap_skills=Counter({"REST API": 32}),
        strength_skills=Counter(),
        skill_role_families={"REST API": Counter({"Technical / product support": 1})},
        gap_shortfalls={"REST API": [40] * 32},
    )

    assert len(rows) == 1

    indicator = rows[0]["evidence_priority_indicator"]

    assert isinstance(indicator, (int, float))
    assert 0 <= indicator <= 10
