from pathlib import Path


def test_playwright_audit_uses_explicit_evaluate_arguments() -> None:
    repository = Path(__file__).resolve().parents[2]
    audit = (repository / "backend" / "src" / "jolt" / "workbench_playwright_audit.py").read_text(
        encoding="utf-8"
    )

    assert "arguments[0]" not in audit
    assert 'page.evaluate("position => window.scrollTo(0, position)", position)' in audit
    assert 'page.evaluate("() => window.scrollTo(0, 0)")' in audit
