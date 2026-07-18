from pathlib import Path


def test_visual_journey_requires_real_loaded_data_and_bounded_review() -> None:
    repository = Path(__file__).resolve().parents[2]
    journey = (
        repository / "backend" / "src" / "jolt" / "playwright_visual_journey.py"
    ).read_text(encoding="utf-8")

    assert "Opportunity API returned no opportunities for visual certification." in journey
    assert "MAX_SCROLL_STEPS = 200" in journey
    assert "for _ in range(MAX_SCROLL_STEPS)" in journey
    assert 'filter(has_text="Readiness report history")' in journey
    assert 'return f"screenshots/{filename}"' in journey
    assert "if browser is not None:" in journey
    assert "browser.close()" in journey


def test_visual_journey_does_not_accept_generic_details_panel() -> None:
    repository = Path(__file__).resolve().parents[2]
    journey = (
        repository / "backend" / "src" / "jolt" / "playwright_visual_journey.py"
    ).read_text(encoding="utf-8")

    assert 'details = page.locator("details")' not in journey
    assert "expand_readiness_history" in journey
    assert "summary.first.click" in journey
