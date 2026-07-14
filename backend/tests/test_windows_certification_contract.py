from pathlib import Path


def test_windows_certification_command_is_path_independent_and_safe() -> None:
    repository = Path(__file__).resolve().parents[2]
    launcher = (repository / "JOLT.ps1").read_text(encoding="utf-8")
    runner = (repository / "tools" / "certify-jolt.ps1").read_text(encoding="utf-8")

    assert '"certify"' in launcher
    assert 'Join-Path $tools "certify-jolt.ps1"' in launcher
    assert "Split-Path -Parent $PSScriptRoot" in runner
    assert "audit-jolt.ps1" in runner
    assert "backup-jolt.ps1" in runner
    assert "restore-jolt.ps1" in runner
    assert "JOLT_CERTIFICATION_" in runner
    assert "JOLT_REVIEW_AUDIT_" in runner
    assert "active_database_overwritten = $false" in runner
    assert "active_database_included = $false" in runner
    assert "backup_database_included = $false" in runner
    assert "restored_database_included = $false" in runner
    assert "Remove-Item -LiteralPath $BackupZip -Force" in runner
    assert "Remove-Item -LiteralPath $RestoreRoot -Recurse -Force" in runner
    assert 'throw "The repository has uncommitted changes.' in runner
