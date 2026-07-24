REPO_ROOT = __import__("pathlib").Path(__file__).parents[2]
PYTHON_AUDIT = REPO_ROOT / "tools" / "jolt-stage-reversal-audit.py"
POWERSHELL_RUNNER = REPO_ROOT / "tools" / "run-jolt-stage-reversal-audit.ps1"


def test_stage_reversal_audit_python_compiles() -> None:
    source = PYTHON_AUDIT.read_text(encoding="utf-8")
    compile(source, str(PYTHON_AUDIT), "exec")


def test_stage_reversal_runner_targets_audit_and_downloads_zip() -> None:
    runner = POWERSHELL_RUNNER.read_text(encoding="utf-8")

    assert "jolt-stage-reversal-audit.py" in runner
    assert "JOLT_STAGE_REVERSAL_AUDIT_$Timestamp.zip" in runner
    assert 'Join-Path $HOME "Downloads"' in runner
    assert "Compress-Archive" in runner
