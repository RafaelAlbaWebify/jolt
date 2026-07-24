REPO_ROOT = __import__("pathlib").Path(__file__).parents[2]
PYTHON_AUDIT = REPO_ROOT / "tools" / "jolt-work-items-audit.py"
POWERSHELL_RUNNER = REPO_ROOT / "tools" / "run-jolt-work-items-audit.ps1"


def test_work_items_audit_python_compiles() -> None:
    source = PYTHON_AUDIT.read_text(encoding="utf-8")
    compile(source, str(PYTHON_AUDIT), "exec")


def test_work_items_audit_runner_targets_python_audit_and_downloads_zip() -> None:
    runner = POWERSHELL_RUNNER.read_text(encoding="utf-8")

    assert "jolt-work-items-audit.py" in runner
    assert "JOLT_WORK_ITEMS_AUDIT_$Timestamp.zip" in runner
    assert 'Join-Path $HOME "Downloads"' in runner
    assert "Compress-Archive" in runner
