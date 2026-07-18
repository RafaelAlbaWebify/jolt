from pathlib import Path


def _journey_source() -> str:
    repository = Path(__file__).resolve().parents[2]
    return (
        repository / "backend" / "src" / "jolt" / "playwright_visual_journey.py"
    ).read_text(encoding="utf-8")


def test_visual_journey_requires_real_loaded_data_and_bounded_review() -> None:
    journey = _journey_source()

    assert "Opportunity API returned no opportunities for visual certification." in journey
    assert "MAX_SCROLL_STEPS = 200" in journey
    assert "for _ in range(MAX_SCROLL_STEPS)" in journey
    assert 'filter(has_text="Readiness report history")' in journey
    assert 'return f"screenshots/{filename}"' in journey


def test_visual_journey_does_not_accept_generic_details_panel() -> None:
    journey = _journey_source()

    assert 'details = page.locator("details")' not in journey
    assert "expand_readiness_history" in journey
    assert "summary.first.click" in journey


def test_visual_journey_always_closes_browser_and_writes_failure_evidence() -> None:
    journey = _journey_source()

    assert "finally:\n            browser.close()" in journey
    assert "except Exception as exc:  # noqa: BLE001" in journey
    assert '"Visual journey crashed: {exc}"' in journey
    assert "_write_summary(args.output_dir, summary)" in journey
    assert '"00-load-timeout.png"' in journey
