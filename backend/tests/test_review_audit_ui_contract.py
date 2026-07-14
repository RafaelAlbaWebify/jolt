from pathlib import Path

from jolt.review_audit import _contains_text


def test_audit_text_matching_is_case_insensitive() -> None:
    rendered = "AUTOMATED PROPOSED DECISION\nApplication readiness"

    assert _contains_text(rendered, "Automated proposed decision")
    assert _contains_text(rendered, "application READINESS")


def test_readiness_history_uses_native_details_contract() -> None:
    source = (Path(__file__).parents[1] / "src" / "jolt" / "review_audit.py").read_text(
        encoding="utf-8"
    )

    assert 'page.locator("details").filter(has_text="Readiness report history")' in source
    assert "element.open = true" in source
    assert 'get_by_role("button", name="Readiness report history")' not in source
